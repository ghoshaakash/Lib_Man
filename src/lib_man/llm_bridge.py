from asyncio import sleep
from google import genai
from google.genai import types
from groq import Groq
import time
from lib_man.config import GetKey


class LLMGen:
    def __init__(self, provider: str = "groq") -> None:

        key_config = GetKey(provider=provider)
        self.key: str = key_config.get_llm_key()

        if provider == "groq":
            self.client = Groq(api_key=self.key)

        elif provider == "google":
            self.client = genai.Client(api_key=self.key)
        self.provider = provider

    def groq_response_gen(self, text: str) -> str | None:
        
        client = Groq(
            api_key=self.key,
            max_retries=0,
        )

        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": text,
                }
            ],
            model="openai/gpt-oss-120b",
        )
        
        
        return chat_completion.choices[0].message.content

    def gemini_response_gen(self, text: str) -> str | None:
        client = genai.Client(
            api_key=self.key,
            http_options=types.HttpOptions(
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )
        interaction = client.interactions.create(model="gemini-4-hydrogen", input=text)
        return interaction.output_text

    def response(self, text: str) -> str | None:
        if self.provider == "groq":
            return self.groq_response_gen(text)
        elif self.provider == "google":
            return self.gemini_response_gen(text)
        else:
            raise RuntimeError("Something has gone horribly wrong and idk how")
