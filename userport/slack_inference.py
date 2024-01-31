import logging
from typing import List
from userport.text_analyzer import TextAnalyzer, AnswerFromSectionsResult
import userport.db
from userport.slack_models import VectorSearchSlackSectionResult


class SlackInference:
    """
    Provides answers to users' questions from Slack.
    """

    def __init__(self) -> None:
        self.text_analyzer = TextAnalyzer(inference=True)
        # Number of documents to return in vector search.
        self.document_limit = 5

    def answer(self, user_query: str, team_id: str) -> str:
        """
        Answer user query by using documentation found in the user's team.
        """
        # Fetch pronouns from given query text.
        user_query_proper_nouns: List[str] = self.text_analyzer.generate_proper_nouns(
            text=user_query)
        logging.info(
            f"Got user query proper nouns: {user_query_proper_nouns} for user query: {user_query}")

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
            user_query_proper_nouns=user_query_proper_nouns,
            document_limit=self.document_limit
        )
        if len(relevant_sections) == 0:
            return self.text_analyzer.get_no_answer_found_text()

        # Generate answer from LLM.
        relevant_text_list: List[str] = [
            self._get_combined_markdown_text(heading=section.heading, text=section.text) for section in relevant_sections]
        answerResult: AnswerFromSectionsResult = self.text_analyzer.generate_answer_to_user_query(
            user_query=user_query, relevant_text_list=relevant_text_list, markdown=True)
        logging.info(f"Information found: {answerResult.information_found}")
        logging.info(f"Chosen text: {answerResult.chosen_section_text}")

        return answerResult.answer_text

    def _get_combined_markdown_text(self, heading: str, text: str) -> str:
        """
        Returns markdown formatted text combining heading and text within a section.
        """
        return f"{heading}\n\n{text}"
