from userport.text_analyzer import TextAnalyzer
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
    # vECTOR Embedding associated with user query.
    user_query_vector_embedding: List[float] = field(default_factory=list)
    # Proper nouns found in user query.
    user_query_proper_nouns: List[str] = field(default_factory=list)
    # Document limit set for vector search.
    document_limit: int = 0
    # Sections returned by vector search.
    sections_with_scores: List[VectorSearchSectionResult] = field(
        default_factory=list)
    # Chosen section by Assistant containing the answer (if any).
    # If None, it means no section was chosen.
    chosen_section: VectorSearchSectionResult = None
    # Final response provided by Assistant.
    final_response: str = ""
    # Inference latency in ms.
    inference_latency: int = 0
    # Exception (if any) encountered during inference.
    exception: str = ""


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

        assistant_inference = InferenceResult(
            user_query=user_query, user_query_context=user_query_context)
        start_time = time.time()
        try:
            # Fetch pronouns from given query text.
            user_query_proper_nouns: List[str] = self.text_analyzer.generate_proper_nouns(
                text=user_query)
            assistant_inference.user_query_proper_nouns = user_query_proper_nouns

            # Fetch embedding for user query.
            user_query_vector_embedding: List[float] = self.text_analyzer.generate_vector_embedding(
                text=user_query)
            assistant_inference.user_query_vector_embedding = user_query_vector_embedding

            # Perform vector search from MongoDB.
            assistant_inference.document_limit = self.document_limit
            assistant_inference.sections_with_scores = vector_search_sections(
                user_org_domain=user_org_domain, query_proper_nouns=user_query_proper_nouns,
                query_vector_embedding=user_query_vector_embedding, document_limit=self.document_limit
            )

            # Perform generation using LLM.

            # Store final result and each step in the pipleine in the db for analysis
            # and algorithm improvement.

        except Exception as e:
            print(e)
            assistant_inference.exception = str(e)

        assistant_inference.inference_latency = int(
            (time.time() - start_time)*1000.0)
        return assistant_inference
