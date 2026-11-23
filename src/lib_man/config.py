import json
import os
import pathlib
from tempfile import TemporaryDirectory

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
        return llm_api_key

    def get_gemini_key(self) -> str:
        llm_api_key = os.getenv("GEMINI_KEY")
        if not llm_api_key:
            raise RuntimeError("GEMINI_KEY environment variable is missing")
        return llm_api_key

    def get_llm_key(self) -> str:
        return self.key


def set_file_cofigs(base_path: pathlib.Path | None = None) -> None:
    if base_path is None:
        base_path = pathlib.Path.cwd()
    while True:
        provider = input("Provider (groq or google): ").strip().lower()
        if provider in {"groq", "google"}:
            break
        print("Enter groq or google.")

    paths = {
        "provider": provider,
        "doc_path": input("Document shelf (blank to skip): ").strip(),
        "paper_path": input("Paper shelf (blank to skip): ").strip(),
        "book_path": input("Book shelf (blank to skip): ").strip(),
    }
    write_file_configs(paths, base_path)


def write_file_configs(config: dict, base_path: pathlib.Path | None = None) -> None:
    if base_path is None:
        base_path = pathlib.Path.cwd()
    file_path = base_path / "file_config.json"
    with TemporaryDirectory(dir=base_path) as temporary:
        pending_config = pathlib.Path(temporary) / file_path.name
        with pending_config.open("w", encoding="utf-8") as file:
            json.dump(config, file, indent=4, ensure_ascii=False)
        pending_config.replace(file_path)


def get_file_configs(base_path: pathlib.Path | None = None) -> dict:
    if base_path is None:
        base_path = pathlib.Path.cwd()
    file_path = base_path / "file_config.json"
    with file_path.open("r", encoding="utf-8") as file:
        return json.load(file)
