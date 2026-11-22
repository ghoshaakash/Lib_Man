from time import sleep

from lib_man.llm_bridge import LLMGen


class PromptAttemptsExhausted(RuntimeError):
    """The provider failed on all three attempts for a prompt."""


class metadataLookup:
    def __init__(self, provider: str) -> None:
        self.LLMGen = LLMGen(provider)

    def _ask(self, prompt: str) -> str | None:
        for attempt in range(1, 4):
            try:
                return self.LLMGen.response(prompt)
            except Exception as error:
                if attempt == 3:
                    raise PromptAttemptsExhausted(
                        "Model request failed after three attempts."
                    ) from error
                sleep(10)

    def get_metadata(self, file_name: str, txt: str) -> dict:

        sort_prompt = f'Classify the file from its first few pages. Use the file name only as a hint. Choose "book" for a book, "paper" for a research paper, or "document" for another kind of document. Choose "unknown" if there is too little evidence to classify it. Return only one lowercase label from the four given options on one line.\nFile name: {file_name}\nFirst few pages:\n{txt}'

        book_sort_prompt = f'Classify the book from its first few pages. Use the file name only as a hint. Choose between "fiction", "non fiction", "academic", and "unknown". Return only one lowercase label on one line.\nFile name: {file_name}\nFirst few pages:\n{txt}'

        name_prompt_book = f"Identify the book's full title from the first few pages, including any subtitle. Use the file name only as a hint. Preserve the original wording and language. Return only the title on one line.\nFile name: {file_name}\nFirst few pages:\n{txt}"

        name_prompt_paper = f"Identify the paper's full title from the first few pages, including any subtitle. Use the file name only as a hint. Preserve the original wording and language. Return only the title on one line.\nFile name: {file_name}\nFirst few pages:\n{txt}"

        name_prompt_document = f"Assign this document a proper title from the first few pages. Use the file name only as a hint. If the document has no explicit title, write a short title that describes its purpose or subject. Use the document's language and return only the title on one line. If the excerpt provides too little information to name the document, return unknown.\nFile name: {file_name}\nFirst few pages:\n{txt}"

        author_prompt_book = f"Identify the book's authors from the first few pages. Use the file name only as a hint. Preserve the original spelling of the names. Return only the author names on one line, separated by underscores for multiple authors. If the authors cannot be determined, return unknown.\nFile name: {file_name}\nFirst few pages:\n{txt}"

        author_prompt_paper = f"Identify the paper's authors from the first few pages. Use the file name only as a hint. Preserve the original spelling of the names. Return only the author names on one line, separated by underscores for multiple authors. If the authors cannot be determined, return unknown.\nFile name: {file_name}\nFirst few pages:\n{txt}"

        year_prompt_book = f'Identify the book\'s edition/year of publication from the first few pages, including any subtitle. Use the file name only as a hint. Preserve the original wording and language. Return only the value on one line. If cannot be determined, return "unknown".\nFile name: {file_name}\nFirst few pages:\n{txt}'

        file_type = (self._ask(sort_prompt) or "").strip().lower()
        metadata = {
            "type": file_type,
            "name": "unknown",
            "author": "unknown",
            "year": "unknown",
        }

        match file_type:
            case "book":
                metadata["name"] = self._ask(name_prompt_book) or "unknown"
                metadata["author"] = self._ask(author_prompt_book) or "unknown"
                metadata["year"] = self._ask(year_prompt_book) or "unknown"
                category = (self._ask(book_sort_prompt) or "").strip().lower()
                metadata["book_category"] = (
                    category
                    if category in {"fiction", "non fiction", "academic"}
                    else "unknown"
                )
            case "paper":
                metadata["name"] = self._ask(name_prompt_paper) or "unknown"
                metadata["author"] = self._ask(author_prompt_paper) or "unknown"
            case "document":
                metadata["name"] = self._ask(name_prompt_document) or "unknown"
            case _:
                metadata["type"] = "unknown"

        return metadata
