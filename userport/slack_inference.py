import logging
from typing import List
import userport.db
from userport.text_analyzer import TextAnalyzer, AnswerFromSectionsResult
from userport.slack_models import VectorSearchSlackSectionResult, SlackSection
from userport.slack_blocks import (
    RichTextBlock,
    RichTextSectionElement,
    RichTextListElement,
    RichTextObject
)
from userport.slack_html_gen import MarkdownToRichTextConverter
import userport.utils


class SlackInference:
    """
    Provides answers to users' questions from Slack.
    """

    def __init__(self, hostname_url: str) -> None:
        self.hostname_url = hostname_url
        self.text_analyzer = TextAnalyzer(inference=True)
        self.markdown_converter = MarkdownToRichTextConverter()
        self.no_sections_found_text = "I'm sorry, I didn't find any documentation that could contain an answer to this question."
        # Number of documents to return in vector search.
        self.document_limit = 5

    def answer(self, user_query: str, team_id: str) -> RichTextBlock:
        """
        Answer user query by using documentation found in the user's team and returns
        answer as a RichTextBlock.
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
            # No relevant sections found.
            # TODO: Add block to ask user to add documentation to capture this answer.
            return self.markdown_converter.convert(self.no_sections_found_text)

        # Generate answer from LLM.
        relevant_text_list: List[str] = [
            self._get_combined_markdown_text(heading=section.heading, text=section.text) for section in relevant_sections]

        answer_result: AnswerFromSectionsResult = self.text_analyzer.generate_answer_to_user_query(
            user_query=user_query, relevant_text_list=relevant_text_list, markdown=True)

        return self._create_answer_block(answer_result=answer_result, relevant_sections=relevant_sections)

    def _create_answer_block(self, answer_result: AnswerFromSectionsResult, relevant_sections: List[SlackSection]) -> RichTextBlock:
        """
        Creates answer block from given Answer result and relevant sections.
        """
        assert len(
            relevant_sections) > 0, f"Expected at least one relevant section, got no sections"
        if not answer_result.information_found:
            return self._create_answer_not_found_block(top_section=relevant_sections[0])

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
                           text="\nSource: "),
            RichTextObject(type=RichTextObject.TYPE_LINK,
                           text=source_section_url_text, url=source_section_url)
        ])
        answer_block.elements.append(answer_source_section)
        return answer_block

    def _create_answer_not_found_block(self, top_section: SlackSection) -> RichTextBlock:
        """
        Creates block that explains answer was not found in given sections.
        """
        answer_block = RichTextBlock(elements=[])

        doc_url = userport.utils.create_documentation_url(
            host_name=self.hostname_url,
            team_domain=top_section.team_domain,
            page_html_id=top_section.page_html_section_id,
            section_html_id=top_section.html_section_id
        )
        no_answer_section = RichTextSectionElement(elements=[
            RichTextObject(type=RichTextObject.TYPE_TEXT,
                           text="I'm sorry, I didn't find an answer to that question in the "),
            RichTextObject(type=RichTextObject.TYPE_LINK,
                           text='documentation.', url=doc_url)
        ])
        answer_block.elements.append(no_answer_section)
        return answer_block

    def _get_combined_markdown_text(self, heading: str, text: str) -> str:
        """
        Returns markdown formatted text combining heading and text within a section.
        """
        return f"{heading}\n\n{text}"
