from userport.text_analyzer import TextAnalyzer, AnswerFromSectionsResult
from userport.db import vector_search_sections
from userport.models import VectorSearchSectionResult
from dataclasses import dataclass, field
from typing import List
import time


@dataclass
class InferenceResult:
    """
    Contains response of inference performed by Assistant.
    """
    # User query.
    user_query: str = ""
    # Context associated with user query.
    user_query_context: List[str] = field(default_factory=list)
    # Vector Embedding associated with user query.
    user_query_vector_embedding: List[float] = field(default_factory=list)
    # Proper nouns found in user query.
    user_query_proper_nouns: List[str] = field(default_factory=list)
    # Document limit set for vector search.
    document_limit: int = 0
    # Relevant Sections returned by vector search.
    relevant_sections: List[VectorSearchSectionResult] = field(
        default_factory=list)
    # Final Text prompt to generate answer. This is created by combining
    # text from the different relevant sections.
    final_text_prompt: str = ""
    # True if information answering user query is found in the sections.
    information_found: bool = False
    # Chosen section text by Assistant containing the answer (if any).
    # If empty, it means no section was chosen.
    chosen_section_text: str = ""
    # Final answer text provided by Assistant.
    answer_text: str = ""
    # Inference latency in ms.
    inference_latency: int = 0
    # Exception (if any) encountered during inference.
    exception_message: str = ""


class InferenceAssistant:
    """
    Responsible for providing answers to queries by performing vector search
    combined with generation.
    """

    def __init__(self) -> None:
        self.text_analyzer = TextAnalyzer()
        # Number of documents to return in vector search.
        self.document_limit = 5

    def answer(self, user_org_domain: str, user_query: str, user_query_context: List[str] = []) -> InferenceResult:
        """
        Understand given user query and context and provides an inference response.
        """

        if_result = InferenceResult(
            user_query=user_query, user_query_context=user_query_context)
        start_time = time.time()
        try:
            # Fetch pronouns from given query text.
            user_query_proper_nouns: List[str] = self.text_analyzer.generate_proper_nouns(
                text=user_query)
            if_result.user_query_proper_nouns = user_query_proper_nouns

            # TODO: We may need to tag the question type (e.g. definition, information, how-to, feedback, troubleshooting etc.).
            # This will help formulate answers better.

            # Fetch embedding for user query.
            user_query_vector_embedding: List[float] = self.text_analyzer.generate_vector_embedding(
                text=user_query)
            if_result.user_query_vector_embedding = user_query_vector_embedding

            print("\nEmbedding and pronoun latency time: ",
                  self.latency_in_ms(start_time), " ms")

            # Perform vector search to find relevant sections.
            if_result.document_limit = self.document_limit
            relevant_sections: List[VectorSearchSectionResult] = vector_search_sections(
                user_org_domain=user_org_domain, query_proper_nouns=user_query_proper_nouns,
                query_vector_embedding=user_query_vector_embedding, document_limit=self.document_limit
            )
            if_result.relevant_sections = relevant_sections

            if len(relevant_sections) > 0:
                # Generate final answer using text from relevant sections.
                final_answer_start_time = time.time()
                relevant_text_list: List[str] = [
                    section.text for section in relevant_sections]

                answerResult: AnswerFromSectionsResult = self.text_analyzer.generate_answer_to_user_query(
                    user_query=user_query, relevant_text_list=relevant_text_list)
                if_result.final_text_prompt = answerResult.prompt
                if_result.information_found = answerResult.information_found
                if_result.chosen_section_text = answerResult.chosen_section_text
                if_result.answer_text = answerResult.answer_text
                print("\nFinal answer generation time: ",
                      self.latency_in_ms(final_answer_start_time), " ms")
            else:
                if_result.answer_text = self.text_analyzer.get_no_answer_found_text()

        except Exception as e:
            print(e)
            if_result.exception_message = str(e)
            if_result.answer_text = "Sorry an internal error occured and I couldn't process your question."

        if_result.inference_latency = self.latency_in_ms(start_time)
        return if_result

    def latency_in_ms(self, start_time):
        return int((time.time() - start_time)*1000.0)