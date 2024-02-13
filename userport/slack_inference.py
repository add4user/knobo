import logging
from typing import List
import userport.db
from userport.text_analyzer import TextAnalyzer, AnswerFromSectionsResult
from userport.slack_models import VectorSearchSlackSectionResult, SlackSection
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

    CREATE_DOC_TEXT = 'Create new documentation'
    CREATE_DOC_ACTION_ID = 'create_doc_action_id'
    CREATE_DOC_VALUE = 'create_doc_answer'
    EDIT_DOC_TEXT = 'Modify existing documentation'
    EDIT_DOC_ACTION_ID = 'edit_doc_action_id'
    EDIT_DOC_VALUE = 'edit_doc_answer'

    def __init__(self, hostname_url: str) -> None:
        self.hostname_url = hostname_url
        self.text_analyzer = TextAnalyzer(inference=True)
        self.markdown_converter = MarkdownToRichTextConverter()
        self.no_sections_found_text = "I'm sorry, I didn't find any documentation that could contain an answer to this question."
        # Number of documents to return in vector search.
        self.document_limit = 5

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

    def answer(self, user_query: str, team_id: str) -> List[MessageBlock]:
        """
        Answer user query by using documentation found in the user's team and returns
        a list of Message blocks.
        """
        # Fetch all nouns from given query text.
        user_query_nouns: List[str] = self.text_analyzer.generate_all_nouns(
            text=user_query)
        logging.info(
            f"Got nouns: {user_query_nouns} in user query: {user_query}")

        # TODO: We may need to tag the question type (e.g. definition, information, how-to, feedback, troubleshooting etc.).
        # This will help formulate answers better.

        # We might want to store topic context whenever proper nouns are not detected in the current query.
        # This way we can apply the previous proper nouns to fitler and provide a better response. The topic context
        # will change whenever new proper nouns are found in the question or maybe we combine the previous proper noun
        # with current proper nouns if there are any pronouns in the question.

        # Fetch embedding for user query.
        user_query_vector_embedding: List[float] = self.text_analyzer.generate_vector_embedding(
            text=user_query)
        logging.info(f"Generated vector embedding for user query {user_query}")

        # Vector search for similar sections.
        relevant_sections: List[VectorSearchSlackSectionResult] = userport.db.vector_search_slack_sections(
            team_id=team_id,
            user_query_vector_embedding=user_query_vector_embedding,
            user_query_proper_nouns=user_query_nouns,
            document_limit=self.document_limit
        )
        if len(relevant_sections) == 0:
            # No relevant sections found, give user option to create new documentation.
            result_blocks: List[MessageBlock] = []
            answer_block: RichTextBlock = self.markdown_converter.convert(
                self.no_sections_found_text)
            result_blocks.append(answer_block)

            buttons_block = Actionsblock(
                elements=[
                    ButtonElement(
                        text=TextObject(
                            type=TextObject.TYPE_PLAIN_TEXT, text=self.CREATE_DOC_TEXT
                        ),
                        action_id=self.CREATE_DOC_ACTION_ID,
                        value=self.CREATE_DOC_VALUE,
                    )
                ]
            )
            result_blocks.append(buttons_block)
            return result_blocks

        # Generate answer from LLM.
        # TODO: We may want to use section summary for Q&A. Section text is good for steps or direct references
        # which may not be stored in summary. If we can combine both in the future, that would reduce false negatives
        # further.
        relevant_text_list: List[str] = [
            self._get_combined_markdown_text(heading=section.heading, text=section.text) for section in relevant_sections]

        answer_result: AnswerFromSectionsResult = self.text_analyzer.generate_answer_to_user_query(
            user_query=user_query, relevant_text_list=relevant_text_list, markdown=True)

        return self._create_answer_block(answer_result=answer_result, relevant_sections=relevant_sections)

    def _create_answer_block(self, answer_result: AnswerFromSectionsResult, relevant_sections: List[SlackSection]) -> List[MessageBlock]:
        """
        Creates answer block from given Answer result and relevant sections.
        """
        assert len(
            relevant_sections) > 0, f"Expected at least one relevant section, got no sections"
        if not answer_result.information_found:
            return self._create_answer_not_found_block(top_section=relevant_sections[0])

        logging.info(
            f"\nChosen answer section index:  {answer_result.chosen_section_index}")
        logging.info(
            f"\nGenerated answer text: {answer_result.answer_text}")

        result_blocks: List[MessageBlock] = []

        # Create answer block from markdown text.
        answer_block: RichTextBlock = self.markdown_converter.convert(
            markdown_text=answer_result.answer_text)

        # Add source section to answer block so user knows where the answer was generated from.
        source_section: SlackSection = relevant_sections[answer_result.chosen_section_index]
        source_section_url: str = userport.utils.create_documentation_url(
            host_name=self.hostname_url,
            team_domain=source_section.team_domain,
            page_html_id=source_section.page_html_section_id,
            section_html_id=source_section.html_section_id
        )
        source_section_url_text: str = f'#{source_section.html_section_id}'
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
                    type=TextObject.TYPE_PLAIN_TEXT, text=self.LIKE_EMOJI, emoji=True
                ),
                action_id=self.LIKE_ACTION_ID,
                value=self.LIKE_VALUE
            ),
            ButtonElement(
                text=TextObject(
                    type=TextObject.TYPE_PLAIN_TEXT, text=self.DISLIKE_EMOJI, emoji=True
                ),
                action_id=self.DISLIKE_ACTION_ID,
                value=self.DISLIKE_VALUE
            ),

        ])
        result_blocks.append(buttons_block)

        return result_blocks

    def _create_answer_not_found_block(self, top_section: SlackSection) -> List[MessageBlock]:
        """
        Creates block that explains answer was not found in given sections.
        """
        result_blocks: List[MessageBlock] = []

        answer_block = RichTextBlock(elements=[])
        # Add documentation URL.
        doc_url = userport.utils.create_documentation_url(
            host_name=self.hostname_url,
            team_domain=top_section.team_domain,
            page_html_id=top_section.page_html_section_id,
            section_html_id=top_section.html_section_id
        )
        no_answer_section = RichTextSectionElement(elements=[
            RichTextObject(type=RichTextObject.TYPE_TEXT,
                           text="I'm sorry, I didn't find an answer to that question in "),
            RichTextObject(type=RichTextObject.TYPE_LINK,
                           text=f'#{top_section.html_section_id}.', url=doc_url),
            RichTextObject(type=RichTextObject.TYPE_TEXT,
                           text='\n\n')
        ])
        answer_block.elements.append(no_answer_section)
        result_blocks.append(answer_block)

        # Add buttons to add or modify documentation.
        buttons_block = Actionsblock(elements=[
            ButtonElement(
                text=TextObject(
                    type=TextObject.TYPE_PLAIN_TEXT, text=self.CREATE_DOC_TEXT
                ),
                action_id=self.CREATE_DOC_ACTION_ID,
                value=self.CREATE_DOC_VALUE,
            ),
            ButtonElement(
                text=TextObject(
                    type=TextObject.TYPE_PLAIN_TEXT, text=self.EDIT_DOC_TEXT
                ),
                action_id=self.EDIT_DOC_ACTION_ID,
                value=self.EDIT_DOC_VALUE,
            ),

        ])
        result_blocks.append(buttons_block)

        return result_blocks

    def _get_combined_markdown_text(self, heading: str, text: str) -> str:
        """
        Returns markdown formatted text combining heading and text within a section.
        """
        return f"{heading}\n\n{text}"
