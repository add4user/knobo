from userport.openai_manager import OpenAIManager
from typing import List
from tenacity import retry, wait_random, stop_after_attempt
from dataclasses import dataclass
from pydantic import BaseModel
from nltk.stem import PorterStemmer
import json
import logging


@dataclass
class AnswerFromSectionsResult:
    # Prompt created for user query.
    prompt: str = ""
    # True if information answering user query is found in the sections, False otherwise.
    information_found: bool = False
    # Chose section's index among relevent sections used to generate the answer.
    chosen_section_index: int = -1
    # Chosen section text by Assistant containing the answer (if any).
    chosen_section_text: str = ""
    # Final answer text provided by Assistant.
    answer_text: str = ""


class TextAnalyzer:
    """
    Contains helpers to summarize text, generate embeddings and generate proper nouns.
    """

    def __init__(self, debug=False, inference: bool = False) -> None:
        self.openai_manager = OpenAIManager()
        self.ps = PorterStemmer()
        if not inference:
            self.system_message = "You are a helpful assistant that answers questions in the most truthful manner possible."
        else:
            self.system_message = "You are a helpful assistant that answers questions in the most truthful manner possible. " +\
                "You also provide concise answers so that users can easily comprehend the answer and then ask follow ups if required. "
        self.json_mode_system_message = self.system_message + \
            " You output results in only JSON."
        self.no_answer_found_text = "I'm sorry, I don't know the answer to that question."
        self.debug = debug

    def get_no_answer_found_text(self):
        """
        Returns no answer for given text message.
        """
        return self.no_answer_found_text

    def generate_detailed_summary_with_context(self, text: str, preceding_text: str, markdown: bool = False):
        """
        Generates detailed summary for given text using the text preceding it as context.
        """
        summary_prompt = self._create_detailed_summary_with_context_prompt(
            text=text, context=preceding_text, markdown=markdown)

        if self.debug:
            logging.info("Summary prompt with context:\n")
            logging.info(summary_prompt)
            logging.info("\n")
        return self._generate_response(summary_prompt)

    def generate_detailed_summary(self, text: str, markdown: bool = False) -> str:
        """
        Generates detailed summary for given text.
        """
        summary_prompt = self._create_summary_prompt(
            text=text, markdown=markdown)

        if self.debug:
            logging.info("Summary prompt:\n")
            logging.info(summary_prompt)
            logging.info("\n")
        return self._generate_response(summary_prompt)

    def generate_concise_summary(self, text: str, markdown: bool = False) -> str:
        """
        Generates concise summary for given text.
        """
        concise_summary_prompt = self._create_concise_summary_prompt(
            text=text, markdown=markdown)

        if self.debug:
            logging.info("Concise Summary prompt:\n")
            logging.info(concise_summary_prompt)
            logging.info("\n")
        return self._generate_response(concise_summary_prompt)

    def generate_vector_embedding(self, text: str) -> List[float]:
        """
        Generate vector embedding for given text.
        """
        return self.openai_manager.get_embedding(text)

    @retry(wait=wait_random(min=1, max=2), stop=stop_after_attempt(3))
    def generate_proper_nouns(self, text: str, markdown: bool = False) -> List[str]:
        """
        Generates proper nouns from given text and returns them
        as a list along with the stemmed versions.
        """
        proper_nouns_prompt = self._create_proper_nouns_prompt(
            text=text, markdown=markdown)

        if self.debug:
            logging.info("Important entities prompt:\n")
            logging.info(proper_nouns_prompt)
            logging.info("\n")

        json_response = self._generate_response(
            prompt=proper_nouns_prompt, json_response=True)

        # Validate the response.
        response_obj = json.loads(json_response)
        assert type(
            response_obj) == dict, f"Expected Response {response_obj} to be type 'dict'"
        assert len(
            response_obj) == 1, f"Expected 1 key in response, got {response_obj} instead"
        # List should be first elem in list of lists.
        proper_nouns_list: List[str] = list(response_obj.values())[0]
        assert type(
            proper_nouns_list) == list, f"Expected Proper nouns to be {proper_nouns_list} to be a list"

        return self.process_nouns(proper_nouns_list)

    @retry(wait=wait_random(min=1, max=2), stop=stop_after_attempt(3))
    def generate_all_nouns(self, text: str) -> List[str]:
        """
        Generate all nouns (common and proper) given text and return them as a result.
        """
        class AllNounsResponse(BaseModel):
            """
            Class to validate nouns generation response.
            """
            nouns: List[str]

        all_nouns_prompt: str = self._generate_all_nouns_prompt(text)
        json_response = self._generate_response(
            prompt=all_nouns_prompt, json_response=True)
        got_nouns = AllNounsResponse(**json.loads(json_response)).nouns
        return self.process_nouns(got_nouns)

    def generate_answer_to_user_query(self, user_query: str, relevant_text_list: List[str], markdown: bool = False) -> AnswerFromSectionsResult:
        """
        Generate answer to user query and relevant text list in JSON mode.
        Returns instance of the AnswerFromSectionsResult class after response validation.

        If markdown is set to true, then it returns answer text in Markdown format.
        """
        prompt: str = self._create_answer_prompt(
            user_query=user_query, relevant_text_list=relevant_text_list, markdown=markdown)
        logging.info(f"Answer prompt: {prompt}")

        result = AnswerFromSectionsResult(prompt=prompt)

        json_response = self._generate_response(
            prompt=prompt, json_response=True)
        response_dict = json.loads(json_response)
        assert type(
            response_dict) == dict, f"Expected Response {response_dict} to be type 'dict' in result: {result}"

        # Validate information_found key.
        info_found_key = "information_found"
        assert info_found_key in response_dict, f"Expected key {info_found_key} in response, got {response_dict} in result: {result}"
        result.information_found = response_dict[info_found_key]

        if not result.information_found:
            result.answer_text = self.no_answer_found_text
            return result

        # Validate answer key.
        answer_key = "answer"
        assert answer_key in response_dict, f"Expected key {answer_key} in response, for {response_dict} in result: {result}"
        result.answer_text = response_dict[answer_key]

        # Validate section_number key.
        section_number_key = "section_number"
        assert section_number_key in response_dict, f"Expected key {section_number_key} in response, for {response_dict} in result: {result}"
        assert type(response_dict[section_number_key]
                    ) == int, f"Expected section number, got {type(response_dict[section_number_key])} for {response_dict} in result: {result}"
        section_number: int = response_dict[section_number_key]
        if section_number < 1 or section_number > len(relevant_text_list):
            raise ValueError(
                f"Section number not in expected range (1, {len(relevant_text_list)}) for {response_dict} in {result}")
        result.chosen_section_text = relevant_text_list[section_number-1]
        result.chosen_section_index = section_number - 1

        return result

    def _generate_response(self, prompt: str, json_response: bool = False) -> str:
        """
        Helper to generate response from OpenAI.
        """
        system_message = self.json_mode_system_message if json_response else self.system_message
        response = self.openai_manager.create_response(
            message=prompt, system_message=system_message, json_response=json_response)
        if self.debug:
            logging.info("Generated response:\n")
            logging.info(response)
            logging.info("\n")
        return response

    def _create_summary_prompt(self, text: str, markdown: bool = False) -> str:
        """
        Helper to create a summary prompt. The prompt is slightly different if
        text is formatted as markdown.
        """
        if not markdown:
            return ('Text:\n'
                    '"""\n'
                    f'{text}\n'
                    '"""\n\n'
                    'Explain in detail.'
                    )

        return ('Text:\n'
                '"""\n'
                f'{text}\n'
                '"""\n\n'
                'Explain the content in this text using only the information in the text. The text is Markdown formatted.'
                )

    def _create_concise_summary_prompt(self, text: str, markdown: bool = False) -> str:
        """
        Helper to create a concise summary prompt.
        """
        if not markdown:
            return ('Text:\n'
                    '"""\n'
                    f'{text}\n'
                    '"""\n\n'
                    'This text is from sequential sections in a document. Explain it in a concise manner.'
                    )
        return ('Text:\n'
                '"""\n'
                f'{text}\n'
                '"""\n\n'
                'This Markdown formatted text is from sequential sections in a document. Explain its content in a concise manner.'
                )

    def _create_detailed_summary_with_context_prompt(self, text: str, context: str, markdown: bool = False) -> str:
        """
        Helper to createsa detailed summary prompt for given text and context. The prompt is slightly different if
        text is formatted as markdown.
        """
        if not markdown:
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

        return ('Preceding text:\n'
                '"""\n'
                f'{context}\n'
                '"""\n\n'
                'Current text:\n'
                '"""\n'
                f'{text}\n'
                '"""\n\n'
                'Explain the content in the current text using preceding text as context. The current text is Markdown formatted. The preceding text is the summary of previous sections in the document.'
                )

    def _create_proper_nouns_prompt(self, text: str, markdown: bool = False) -> str:
        """
        Helper to create important entities prompt for given text. The prompt is slightly different if
        text is formatted as markdown.
        """
        if not markdown:
            return ('Text:\n'
                    '"""\n'
                    f'{text}\n'
                    '"""\n\n'
                    'Extract the proper nouns from this text and return the result as an array.'
                    )

        return ('Text:\n'
                '"""\n'
                f'{text}\n'
                '"""\n\n'
                'Extract the proper nouns from this Markdown formatted text and return the result as an array.'
                )

    def _generate_all_nouns_prompt(self, text: str) -> str:
        """
        Return prompt to generate all nouns (proper and common) from given text.
        """
        return ('Text:\n'
                '"""\n'
                f'{text}\n'
                '"""\n\n'
                'Extract all nouns from this text and return the result in a JSON object.'
                ' They JSON object should contain a field "nouns" of type of Array containing all the nouns found.'
                )

    def _create_answer_prompt(self, user_query: str, relevant_text_list: List[str], markdown: bool = False) -> str:
        """
        Helper to create answer from given user query and list of relevant text.
        """
        formatted_text_list: List[str] = []
        for i, relevant_text in enumerate(relevant_text_list):
            formatted_text = (f'Section {i+1}\n'
                              '"""\n'
                              f'{relevant_text}\n'
                              '"""\n\n')
            formatted_text_list.append(formatted_text)

        formatted_user_query = ('User query\n'
                                '"""\n'
                                f'{user_query}\n'
                                '""\n\n')
        formatted_text_list.append(formatted_user_query)

        prompt = ''
        if not markdown:
            prompt = ('Answer the User query using only the information in the Sections above.'
                      ' Return the result as a JSON object with "information_found" as boolean field, "answer" as string field and "section_number" as int field.'
                      ' The "information_found" field should be set to false if the answer is not contained in the Sections above.'
                      ' Do not mention the the Section number in the "answer" field.')
        else:
            prompt = ('Answer the User query using only the information in the Sections above.'
                      ' Return the result as a JSON object with "information_found" as boolean field, "answer" as string field and "section_number" as int field.'
                      ' The "information_found" field should be set to false if the answer is not contained in the Sections above.'
                      ' The "answer" field should be Markdown formatted text.'
                      ' Do not mention the the Section number in the "answer" field.')
        formatted_text_list.append(prompt)
        return "\n".join(formatted_text_list)

    def process_nouns(self, nouns_list: List[str]) -> List[str]:
        """
        Since MongoDB allows mostly comparison operators in search query, we plan to use $in operator
        when filtering for docs during vector search. To use $in operator, each word in the list must be
        comparable and processing steps like [1] splitting into multi word and [2] stemming are not implemented
        out of the box unlike in full text search.

        This method is to perform this processing so sections are searchable with fewer false negatives.
        Some of the work done here are:
        1. Split multi-word nouns into separate words in the list.
        2. Stemming each single word.
        """
        final_nouns_set = set()
        for noun in nouns_list:
            final_nouns_set.add(noun)
            for word in noun.split():
                final_nouns_set.add(word)
                final_nouns_set.add(self.ps.stem(word))

        return list(final_nouns_set)
