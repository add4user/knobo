from userport.openai_manager import OpenAIManager
from typing import List
from tenacity import retry, wait_random, stop_after_attempt
import json


class TextAnalyzer:
    """
    Contains helpers to summarize text, generate embeddings and generate proper nouns.
    """

    def __init__(self, debug=False) -> None:
        self.openai_manager = OpenAIManager()
        self.system_message = "You are a helpful assistant that answers questions in the most truthful manner possible."
        self.json_mode_system_message = self.system_message + \
            " You output results in only JSON."
        self.debug = debug

    def generate_detailed_summary_with_context(self, text: str, preceding_text: str):
        """
        Generates detailed summary for given text using the text preceding it as context.
        """
        summary_prompt = self._create_detailed_summary_with_context_prompt(
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
        summary_prompt = self._create_summary_prompt(text)

        if self.debug:
            print("Summary prompt:\n")
            print(summary_prompt)
            print("\n")
        return self._generate_response(summary_prompt)

    def generate_concise_summary(self, text: str) -> str:
        """
        Generates concise summary for given text.
        """
        concise_summary_prompt = self._create_concise_summary_prompt(text)

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

    @retry(wait=wait_random(min=1, max=2), stop=stop_after_attempt(3))
    def generate_proper_nouns(self, text: str) -> List[str]:
        """
        Generates proper nouns from given text and returns them
        as a list.
        """
        important_entities_prompt = self._create_proper_nouns_prompt(text)

        if self.debug:
            print("Important entities prompt:\n")
            print(important_entities_prompt)
            print("\n")

        json_response = self._generate_response(
            prompt=important_entities_prompt, json_response=True)
        response_obj = json.loads(json_response)
        assert type(
            response_obj) == dict, f"Expected Response {response_obj} to be type 'dict'"
        assert len(
            response_obj) == 1, f"Expected 1 key in response, got {response_obj} instead"
        # List should be first elem in list of lists.
        proper_nouns_list: List[str] = list(response_obj.values())[0]
        assert type(
            proper_nouns_list) == list, f"Expected Proper nouns to be {proper_nouns_list} to be a list"
        return proper_nouns_list

    def _generate_response(self, prompt: str, json_response: bool = False) -> str:
        """
        Helper to generate response from OpenAI.
        """
        system_message = self.json_mode_system_message if json_response else self.system_message
        response = self.openai_manager.create_response(
            message=prompt, system_message=system_message, json_response=json_response)
        if self.debug:
            print("Generated response:\n")
            print(response)
            print("\n")
        return response

    def _create_summary_prompt(self, text: str) -> str:
        """
        Helper to create a summary prompt.
        """
        return ('Text:\n'
                '"""\n'
                f'{text}\n'
                '"""\n\n'
                'Explain in detail.'
                )

    def _create_concise_summary_prompt(self, text: str) -> str:
        """
        Helper to create a concise summary prompt.
        """
        return ('Text:\n'
                '"""\n'
                f'{text}\n'
                '"""\n\n'
                'This text is from sequential sections in a document. Explain it in a concise manner.'
                )

    def _create_detailed_summary_with_context_prompt(self, text: str, context: str) -> str:
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

    def _create_proper_nouns_prompt(self, text: str) -> str:
        """
        Helper to create important entities prompt for given text.
        """
        return ('Text:\n'
                '"""\n'
                f'{text}\n'
                '"""\n\n'
                'Extract the proper nouns from this text and return the result as an array.'
                )


if __name__ == "__main__":
    text_analyzer = TextAnalyzer(debug=True)
    text = (
        'How to Index the Elements of an Array\n\n'
        'For indexing arrays, Atlas Search requires only the data type of the array elements. '
        "You don't have to specify that the data is contained in an array ([]) in the index definition."
        'If you enable dynamic mappings, Atlas Search automatically indexes elements of dynamically indexable data types inside the array.'
        'To learn more about the data types that Atlas Search dynamically indexes, see Data Types.\n\n'
        'You can use the Visual Editor or the JSON Editor in the Atlas UI to define the index for elements in arrays.'
    )

    proper_nouns = text_analyzer.generate_proper_nouns(text)
    print("got proper nouns: ", proper_nouns)
