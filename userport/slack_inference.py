import logging
from typing import List, Dict, Optional
import userport.db
import json
from pydantic import BaseModel
from userport.text_analyzer import TextAnalyzer, LLMResult
from userport.slack_models import VS3Record, VS3Result
from userport.slack_blocks import (
    RichTextBlock,
    MessageBlock,
    Actionsblock,
    ButtonElement,
    RichTextSectionElement,
    RichTextObject,
    TextObject
)
from userport.slack_html_gen import MarkdownToRichTextConverter
import userport.utils
from userport.utils import get_slack_web_client, get_hostname_url
from celery import shared_task, chord


class SlackInferenceRequest(BaseModel):
    """
    Simpler container to hold all input parameters
    used during inference.
    """
    user_query: str
    team_id: str
    channel_id: str
    user_id: str
    private_visibility: bool
    vs3_result: Optional[VS3Result] = None
    document_limit: int = 5


class SlackInference:
    """
    Provides answers to users' questions from Slack.
    """
    LIKE_EMOJI = ":thumbsup:"
    DISLIKE_EMOJI = ":thumbsdown:"

    LIKE_ACTION_ID = 'like_action_id'
    LIKE_VALUE = 'like_answer'
    DISLIKE_ACTION_ID = 'dislike_action_id'
    DISLIKE_VALUE = 'dislike_answer'

    CREATE_DOC_TEXT = 'Create a new section'
    CREATE_DOC_ACTION_ID = 'create_doc_action_id'
    CREATE_DOC_VALUE = 'create_doc_answer'
    EDIT_DOC_TEXT = 'Edit existing section'
    EDIT_DOC_ACTION_ID = 'edit_doc_action_id'
    EDIT_DOC_VALUE = 'edit_doc_answer'

    NO_SECTIONS_FOUND_TEXT = "I'm sorry, I didn't find any sections that could contain an answer to this question."

    @staticmethod
    def get_create_doc_action_id() -> str:
        """
        Returns actions ID associatedw with create documentation.
        """
        return SlackInference.CREATE_DOC_ACTION_ID

    @staticmethod
    def get_edit_doc_action_id() -> str:
        """
        Returns actions ID associatedw with edit documentation.
        """
        return SlackInference.EDIT_DOC_ACTION_ID

    def answer(request: SlackInferenceRequest):
        """
        Answering user query within a given team by parallelizing calls to
        LLM in order to increase accuracy and reduce latency.

        Returns a list of Dictionaries of Slack message blocks containing the formatted answer.
        We return dictionaries since worker tasks need to return serializable objects.
        """

        # TODO: We may need to tag the question type (e.g. definition, information, how-to, feedback, troubleshooting etc.).
        # This will help formulate answers better.

        # We might want to store topic context whenever proper nouns are not detected in the current query.
        # This way we can apply the previous proper nouns to fitler and provide a better response. The topic context
        # will change whenever new proper nouns are found in the question or maybe we combine the previous proper noun
        # with current proper nouns if there are any pronouns in the question.

        # Compute in parallel.
        header = [SlackInference._gen_query_nouns_async.s(request.user_query),
                  SlackInference._gen_query_embedding_async.s(request.user_query)]
        callback = SlackInference.fetch_answer_from_sections.s(
            request_json=request.model_dump_json())

        # Invoke chord.
        chord(header)(callback)

    @shared_task
    def fetch_answer_from_sections(prev_result_list, request_json: str) -> List[Dict]:
        request = SlackInferenceRequest(**json.loads(request_json))

        query_nouns: List[str] = prev_result_list[0]
        query_vector_embedding: List[float] = prev_result_list[1]

        # Need to wait for results from queries above since it is needed for vector search.
        logging.info(
            f"Got nouns: {query_nouns} in user query: {request.user_query}")

        logging.info(
            f"Generated vector embedding for user query {request.user_query}")

        # Vector search for similar sections.
        vs3_result: VS3Result = userport.db.vector_search_slack_sections(
            team_id=request.team_id,
            user_query_vector_embedding=query_vector_embedding,
            user_query_proper_nouns=query_nouns,
            document_limit=request.document_limit
        )
        request.vs3_result = vs3_result

        logging.info(
            f"Vector search results: {[record.heading for record in vs3_result.records]}")

        # Use chord to compute multiple LLM results in parallel.
        llm_results_header = []
        for record in vs3_result.records:
            llm_results_header.append(SlackInference.compute_llm_result_async.s(
                user_query=request.user_query,
                reference_text=SlackInference._get_combined_markdown_text(
                    heading=record.heading, text=record.text),
            ))
        callback = SlackInference.process_llm_results.s(
            request_json=request.model_dump_json())

        # Invoke chord.
        return chord(llm_results_header)(callback)

    @shared_task
    def process_llm_results(llm_results_json: List[str], request_json: str):
        """
        Process all LLM results and posts answer to Slack.

        This is the final celery task to execute inference.
        """
        llm_results: List[LLMResult] = []
        for section_result_json in llm_results_json:
            llm_results.append(
                LLMResult(**json.loads(section_result_json)))
        request = SlackInferenceRequest(**json.loads(request_json))
        vs3_records = request.vs3_result.records

        if len(vs3_records) == 0:
            # No sections found in vector search.
            SlackInference._post_answer_to_slack(
                answer_blocks=SlackInference._no_records_found(),
                request=request
            )
            return

        # Compute indices of VS3 records that have answers according to the LLM.
        # The assumption is that LLM results are in the same order as VS3 records.
        # We will use these indices to reference the VS3 records as source of truth
        # in the final answer.
        record_indices_with_answers: List[int] = []
        for i, llm_result in enumerate(llm_results):
            if llm_result.information_found:
                record_indices_with_answers.append(i)
        if len(record_indices_with_answers) == 0:
            # None of the VS3 records contained the answer, indicate this in the
            # answer and link the first record as evidence.
            # TODO: Wonder if it is worth searching for next page of VS3 records for the answer.
            SlackInference._post_answer_to_slack(
                answer_blocks=SlackInference._create_answer_not_found_in_record(
                    vs3_records[0]),
                request=request
            )
            return

        logging.info(
            f'Found answers in VS3 indices: {record_indices_with_answers}')

        # For now select first index where answer is found.
        # TODO: Make this more sophisticated in the future where we can combine
        # answers from multiple sections if need be.
        selected_idx: LLMResult = record_indices_with_answers[0]
        llm_result = llm_results[selected_idx]
        reference_record = vs3_records[selected_idx]
        SlackInference._post_answer_to_slack(
            answer_blocks=SlackInference._create_answer_found(
                llm_result=llm_result,
                reference_record=reference_record,
            ),
            request=request
        )

    @shared_task
    def _gen_query_nouns_async(user_query: str) -> List[str]:
        """
        Async version of generating nouns from given user query.

        Run in a celery task to make the operation async.
        """
        text_analyzer = TextAnalyzer(inference=True)
        return text_analyzer.generate_all_nouns(text=user_query)

    @shared_task
    def _gen_query_embedding_async(user_query: str) -> List[float]:
        """
        Async version of generating embedding of given user query.

        Run in a celery task to make the operation async.
        """
        text_analyzer = TextAnalyzer(inference=True)
        return text_analyzer.generate_vector_embedding(text=user_query)

    @shared_task
    def compute_llm_result_async(user_query: str, reference_text: str) -> str:
        """
        Computes whether reference text contains answer to user query.
        We return a JSON string of LLMResult because it needds to be serialized
        in worker processes.

        Run in a celery task to make the operation aync.
        """
        text_analyzer = TextAnalyzer(inference=True)
        llm_result: LLMResult = text_analyzer.answer_user_query(
            user_query=user_query, reference_text=reference_text)
        return llm_result.model_dump_json()

    @staticmethod
    def _no_records_found() -> List[MessageBlock]:
        """
        Returns list of answer blocks explaining no VS3 records were retrieved for user query.
        """
        result_blocks: List[MessageBlock] = []
        markdown_converter = MarkdownToRichTextConverter()

        answer_block: RichTextBlock = markdown_converter.convert(
            SlackInference.NO_SECTIONS_FOUND_TEXT)
        result_blocks.append(answer_block)

        # No relevant sections found, give user option to create new documentation to fill gap.
        buttons_block = Actionsblock(
            elements=[
                ButtonElement(
                    text=TextObject(
                        type=TextObject.TYPE_PLAIN_TEXT, text=SlackInference.CREATE_DOC_TEXT
                    ),
                    action_id=SlackInference.CREATE_DOC_ACTION_ID,
                    value=SlackInference.CREATE_DOC_VALUE,
                )
            ]
        )
        result_blocks.append(buttons_block)
        return result_blocks

    @staticmethod
    def _create_answer_not_found_in_record(top_record: VS3Record) -> List[MessageBlock]:
        """
        Returns answer blocks that explains answer was not found in given top record.
        """
        result_blocks: List[MessageBlock] = []

        answer_block = RichTextBlock(elements=[])
        # Add documentation URL.
        doc_url = userport.utils.create_documentation_url(
            host_name=get_hostname_url(),
            team_domain=top_record.team_domain,
            page_html_id=top_record.page_html_section_id,
            section_html_id=top_record.html_section_id,
        )
        no_answer_section = RichTextSectionElement(elements=[
            RichTextObject(type=RichTextObject.TYPE_TEXT,
                           text="I'm sorry, I didn't find an answer to that question in "),
            RichTextObject(type=RichTextObject.TYPE_LINK,
                           text=f'#{top_record.html_section_id}.', url=doc_url),
            RichTextObject(type=RichTextObject.TYPE_TEXT,
                           text='\n\n')
        ])
        answer_block.elements.append(no_answer_section)
        result_blocks.append(answer_block)

        # Add buttons to add or modify documentation.
        buttons_block = Actionsblock(elements=[
            ButtonElement(
                text=TextObject(
                    type=TextObject.TYPE_PLAIN_TEXT, text=SlackInference.CREATE_DOC_TEXT
                ),
                action_id=SlackInference.CREATE_DOC_ACTION_ID,
                value=SlackInference.CREATE_DOC_VALUE,
            ),
            ButtonElement(
                text=TextObject(
                    type=TextObject.TYPE_PLAIN_TEXT, text=SlackInference.EDIT_DOC_TEXT
                ),
                action_id=SlackInference.EDIT_DOC_ACTION_ID,
                value=SlackInference.EDIT_DOC_VALUE,
            ),

        ])
        result_blocks.append(buttons_block)
        return result_blocks

    @staticmethod
    def _create_answer_found(llm_result: LLMResult, reference_record: VS3Record) -> List[MessageBlock]:
        """
        Return answer blocks given LLM result based on reference VS3 record as knowledge base.
        """
        logging.info(
            f"\nGenerated answer text: {llm_result.answer}")

        result_blocks: List[MessageBlock] = []

        # Create answer block from markdown text.
        markdown_converter = MarkdownToRichTextConverter()
        answer_block: RichTextBlock = markdown_converter.convert(
            markdown_text=llm_result.answer)

        # Add source section to answer block so user knows where the answer was generated from.
        source_section_url: str = userport.utils.create_documentation_url(
            host_name=get_hostname_url(),
            team_domain=reference_record.team_domain,
            page_html_id=reference_record.page_html_section_id,
            section_html_id=reference_record.html_section_id
        )
        source_section_url_text: str = f'#{reference_record.html_section_id}'
        answer_source_section = RichTextSectionElement(elements=[
            RichTextObject(type=RichTextObject.TYPE_TEXT,
                           text="\nSource : "),
            RichTextObject(type=RichTextObject.TYPE_LINK,
                           text=source_section_url_text, url=source_section_url)
        ])
        answer_block.elements.append(answer_source_section)
        result_blocks.append(answer_block)

        # Add Like and dislike button to get feedback.
        buttons_block = Actionsblock(elements=[
            ButtonElement(
                text=TextObject(
                    type=TextObject.TYPE_PLAIN_TEXT, text=SlackInference.LIKE_EMOJI, emoji=True
                ),
                action_id=SlackInference.LIKE_ACTION_ID,
                value=SlackInference.LIKE_VALUE
            ),
            ButtonElement(
                text=TextObject(
                    type=TextObject.TYPE_PLAIN_TEXT, text=SlackInference.DISLIKE_EMOJI, emoji=True
                ),
                action_id=SlackInference.DISLIKE_ACTION_ID,
                value=SlackInference.DISLIKE_VALUE
            ),

        ])
        result_blocks.append(buttons_block)
        return result_blocks

    @staticmethod
    def _post_answer_to_slack(answer_blocks: List[MessageBlock], request: SlackInferenceRequest):
        """
        Helper to post answer blocks to Slack.
        """
        answer_dicts = [block.model_dump(
            exclude_none=True) for block in answer_blocks]

        web_client = get_slack_web_client()
        if request.private_visibility:
            # Post ephemeral message.
            web_client.chat_postEphemeral(
                channel=request.channel_id,
                user=request.user_id,
                blocks=answer_dicts,
            )
        else:
            # Post public message.
            # User user_id as channel argument for IMs per: https://api.slack.com/methods/chat.postMessage#app_home
            # TODO: Change this once we can post public messages in channels as well (in addtion to just IMs). Be careful
            # to not respond to bot posted messages and enter into a recursive loop like we observed in DMs.
            web_client.chat_postMessage(
                channel=request.user_id,
                blocks=answer_dicts
            )

    def _get_combined_markdown_text(heading: str, text: str) -> str:
        """
        Returns markdown formatted text combining heading and text within a section.
        """
        return f"{heading}\n\n{text}"
