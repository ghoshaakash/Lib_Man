import os

from dotenv import load_dotenv

load_dotenv()


class GetKey:
    def __init__(self, provider="groq") -> None:

        self.key: str

        if provider == "groq":
            self.key = self.get_groq_key()
        elif provider == "google":
            self.key = self.get_gemini_key()
        else:
            raise RuntimeError("Provider not supported")

    def get_groq_key(self) -> str:
        llm_api_key = os.getenv("GROQ_KEY")
        if not llm_api_key:
            raise RuntimeError("GROQ_KEY environment variable is missing")

        print("\n Key ending with ...." + llm_api_key[-3:] + " imported succesfully")
        return llm_api_key

    def get_gemini_key(self) -> str:
        llm_api_key = os.getenv("GEMINI_KEY")
        if not llm_api_key:
            raise RuntimeError("GEMINI_KEY environment variable is missing")

        print("\n Key ending with ...." + llm_api_key[-3:] + " imported succesfully")
        return llm_api_key

    def get_llm_key(self) -> str:
        return self.key
