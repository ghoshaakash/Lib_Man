import json
import os
import time
from asyncio import sleep
from urllib.request import Request, urlopen

from google import genai
from google.genai import types
from groq import Groq

from lib_man.config import GetKey


class LLMGen:
    def __init__(self, provider: str = "groq") -> None:
        self.provider = provider
        if provider == "ollama":
            self.ollama_model = os.getenv("OLLAMA_MODEL") or "qwen3:4b-instruct"
            return

        key_config = GetKey(provider=provider)
        self.key: str = key_config.get_llm_key()

        if provider == "groq":
            self.client = Groq(api_key=self.key)

        elif provider == "google":
            self.client = genai.Client(api_key=self.key)

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

    def ollama_response_gen(self, text: str) -> str:
        payload = {
            "model": self.ollama_model,
            "messages": [{"role": "user", "content": text}],
            "stream": False,
        }
        request = Request(
            "http://127.0.0.1:11434/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=120) as response:
            content = json.load(response)["message"]["content"]
        if not isinstance(content, str):
            raise RuntimeError("Ollama returned a non-text response.")
        return content

    def response(self, text: str) -> str | None:
        if self.provider == "groq":
            return self.groq_response_gen(text)
        elif self.provider == "google":
            return self.gemini_response_gen(text)
        elif self.provider == "ollama":
            return self.ollama_response_gen(text)
        else:
            raise RuntimeError("Something has gone horribly wrong and idk how")
