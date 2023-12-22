from userport.openai_manager import OpenAIManager
from typing import List


class TextAnalyzer:
    """
    Contains helpers to summarize text, generate embeddings and
    return important entities.
    """

    def __init__(self, debug=False) -> None:
        self.openai_manager = OpenAIManager()
        self.debug = debug

    def generate_detailed_summary_with_context(self, text: str, preceding_text: str):
        """
        Generates detailed summary for given text using the text preceding it as context.
        """
        summary_prompt = self.create_detailed_summary_with_context_prompt(
            text, preceding_text)

        if self.debug:
            print("Summary prompt with context:\n")
            print(summary_prompt)
            print("\n")
        return self._generate_response(summary_prompt)

    def generate_detailed_summary(self, text: str) -> str:
        """
        Generates detailed summary for given text.
        """
        summary_prompt = self.create_summary_prompt(text)

        if self.debug:
            print("Summary prompt:\n")
            print(summary_prompt)
            print("\n")
        return self._generate_response(summary_prompt)

    def generate_concise_summary(self, text: str) -> str:
        """
        Generates concise summary for given text.
        """
        concise_summary_prompt = self.create_concise_summary_prompt(text)

        if self.debug:
            print("Concise Summary prompt:\n")
            print(concise_summary_prompt)
            print("\n")
        return self._generate_response(concise_summary_prompt)

    def generate_vector_embedding(self, text: str) -> List[float]:
        """
        Generate vector embedding for given text.
        """
        return self.openai_manager.get_embedding(text)

    def _generate_response(self, prompt: str) -> str:
        """
        Helper to generate response from OpenAI.
        """
        response = self.openai_manager.create_response(
            message=prompt)
        if self.debug:
            print("Generated response:\n")
            print(response)
            print("\n")
        return response

    def create_summary_prompt(self, text: str) -> str:
        """
        Helper to create a summary prompt.
        """
        return ('Text:\n'
                '"""\n'
                f'{text}\n'
                '"""\n\n'
                'Explain in detail.'
                )

    def create_concise_summary_prompt(self, text: str):
        """
        Helper to create a concise summary prompt.
        """
        return ('Text:\n'
                '"""\n'
                f'{text}\n'
                '"""\n\n'
                'This text is from sequential sections in a document. Explain it in a concise manner.'
                )

    def create_detailed_summary_with_context_prompt(self, text: str, context: str):
        """
        Helper to createsa detailed summary prompt for given text and context.
        """
        return ('Preceding text:\n'
                '"""\n'
                f'{context}\n'
                '"""\n\n'
                'Current text:\n'
                '"""\n'
                f'{text}\n'
                '"""\n\n'
                'Explain in detail the current text using preceding text as context. The preceding text is the summary of previous sections in the document.'
                )
