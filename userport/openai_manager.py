import os
import tiktoken
from openai import OpenAI
from typing import List
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types import CompletionChoice, CreateEmbeddingResponse, Embedding
from tenacity import retry, wait_random, stop_after_attempt
from dotenv import load_dotenv
load_dotenv()  # take environment variables from .env.


class OpenAIManager:
    """
    Class that manages API calls to Open AI.
    """

    def __init__(self) -> None:
        self.client = OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),
        )
        self.chat_model = os.environ.get("OPENAI_CHAT_MODEL")
        self.embedding_model = os.environ.get("OPENAI_EMBEDDING_MODEL")
        self.JSON_RESPONSE_FORMAT = {"type": "json_object"}

    @retry(wait=wait_random(min=1, max=2), stop=stop_after_attempt(3))
    def create_response(self, message: str, system_message: str, json_response: bool = False, temperature: float = 1.0) -> str:
        """
        Creates response for given input message. 
        """
        messages = [
            {
                "role": "system",
                "content": system_message
            },
            {
                "role": "user",
                "content": message,
            }
        ]

        chat_completion: ChatCompletion
        if not json_response:
            chat_completion = self.client.chat.completions.create(
                messages=messages,
                model=self.chat_model,
                n=1,
                temperature=temperature,
            )
        else:
            chat_completion = self.client.chat.completions.create(
                messages=messages,
                model=self.chat_model,
                response_format=self.JSON_RESPONSE_FORMAT,
                n=1,
                temperature=temperature,
            )

        if len(chat_completion.choices) != 1:
            raise ValueError(
                f'Expected 1 response in chat completion response, got {len(chat_completion.choices)} responses')
        chat_completion_choice: CompletionChoice = chat_completion.choices[0]
        if chat_completion_choice.finish_reason != "stop":
            raise ValueError(
                f"Expected finish_reason:'stop', got f{chat_completion_choice.finish_reason}")
        chat_completion_message: ChatCompletionMessage = chat_completion_choice.message
        return chat_completion_message.content

    @retry(wait=wait_random(min=1, max=2), stop=stop_after_attempt(3))
    def get_embedding(self, text: str) -> List[float]:
        """
        Returns an embedding vector for given text input.
        """
        response: CreateEmbeddingResponse = self.client.embeddings.create(
            input=text,
            model=self.embedding_model,
        )
        if len(response.data) != 1:
            raise ValueError(
                f"Expected 1 embeddding response, found f{len(response.data)} responses")
        embedding_obj: Embedding = response.data[0]
        return embedding_obj.embedding

    def num_tokens_from_messages(self, messages, model):
        """
        Return the number of tokens used by a list of messages.
        Copied from Open AI Notebook: https://github.com/openai/openai-cookbook/blob/main/examples/How_to_count_tokens_with_tiktoken.ipynb
        """
        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            # print('Warning: model not found. Using cl100k_base encoding')
            encoding = tiktoken.get_encoding("cl100k_base")
        if model in {
            "gpt-3.5-turbo-0613",
            "gpt-3.5-turbo-16k-0613",
            "gpt-4-0314",
            "gpt-4-32k-0314",
            "gpt-4-0613",
            "gpt-4-32k-0613",
        }:
            tokens_per_message = 3
            tokens_per_name = 1
        elif model == "gpt-3.5-turbo-0301":
            # every message follows <|start|>{role/name}\n{content}<|end|>\n
            tokens_per_message = 4
            tokens_per_name = -1  # if there's a name, the role is omitted
        elif "gpt-3.5-turbo" in model:
            # print(
            # "Warning: gpt-3.5-turbo may update over time. Returning num tokens assuming gpt-3.5-turbo-0613.")
            return self.num_tokens_from_messages(messages, model="gpt-3.5-turbo-0613")
        elif "gpt-4" in model:
            # print(
            # "Warning: gpt-4 may update over time. Returning num tokens assuming gpt-4-0613.")
            return self.num_tokens_from_messages(messages, model="gpt-4-0613")
        else:
            raise NotImplementedError(
                f"""num_tokens_from_messages() is not implemented for model {model}. See https://github.com/openai/openai-python/blob/main/chatml.md for information on how messages are converted to tokens."""
            )
        num_tokens = 0
        for message in messages:
            num_tokens += tokens_per_message
            for key, value in message.items():
                num_tokens += len(encoding.encode(value))
                if key == "name":
                    num_tokens += tokens_per_name
        num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
        return num_tokens


if __name__ == "__main__":
    openai_manager = OpenAIManager()
    # response = openai_manager.create_response("What is the capital of India?")
    # print(response)
    embedding_vector = openai_manager.get_embedding(
        "What is the capital of India?")
    print(embedding_vector)
