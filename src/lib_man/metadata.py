import re
from time import sleep

from lib_man.llm_bridge import LLMGen

_YEAR = re.compile(r"(?<![\w-])([1-9][0-9]{3})(?:-[0-9]{2}-[0-9]{2})?(?![\w-])")
_EDITION_LABEL = (
    r"(?:[0-9]+(?:st|nd|rd|th)|first|second|third|fourth|fifth|sixth|seventh|"
    r"eighth|ninth|tenth|revised|expanded)\s+edition"
)
_TITLE_EDITION = re.compile(
    rf"(?:\s*\({_EDITION_LABEL}\)|\s*[,;:–—-]\s*{_EDITION_LABEL})$", re.IGNORECASE
)


def book_title(value: str) -> str:
    return _TITLE_EDITION.sub("", value.strip()).strip()


def publication_year(value: str, title: str = "") -> str:
    value = value.strip()
    if match := _YEAR.fullmatch(value):
        return match[1]
    if title:
        value = re.sub(re.escape(title), "", value, count=1, flags=re.IGNORECASE)
    years = set(_YEAR.findall(value))
    return years.pop() if len(years) == 1 else ""


def volume_number(value: str) -> str:
    match = re.fullmatch(
        r"(?:(?:vol(?:ume)?\.?|v\.?|#)\s*)?([0-9]{1,3})", value, re.IGNORECASE
    )
    return match[1].zfill(3) if match else ""


def _fiction_metadata(reply: str) -> dict[str, str]:
    stem = " ".join(reply.split()).strip("`")
    fields = [field.strip() for field in stem.split("_", 3)]
    if len(fields) == 4 and fields[0].casefold().startswith("vol "):
        volume, series, title, author = fields
        if (number := volume_number(volume)) and series and title:
            return {
                "name": book_title(title) or "unknown",
                "author": author or "unknown",
                "series": series,
                "series_number": number,
            }
        return {}

    title, separator, author = stem.partition("_")
    if separator:
        return {
            "name": book_title(title) or "unknown",
            "author": author.strip() or "unknown",
        }
    return {}


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

        book_context = f"\nFile name: {file_name}\nFirst few pages:\n{txt}"
        book_sort_prompt = (
            "Classify the book by its main purpose. Choose academic for scholarly "
            "books, textbooks, technical references, and hands-on programming guides, "
            "including books written for self-study. For example, a guide to coding "
            "and training a language model from scratch is academic. Choose fiction "
            "for imaginative literature or non fiction for other factual books. "
            "Use the file name only as a hint. If the purpose is unclear, choose unknown. "
            "Return only the lowercase label."
            f"{book_context}"
        )

        name_prompt_book = (
            "Return only the book title and subtitle as printed on the title page, "
            "preserving the original wording, language, capitalization, and parentheses. "
            "Leave out edition labels, series names, authors, publishers, and publication "
            "years unless they are part of the title itself. Use the file name only as a hint. "
            "Return unknown if you cannot identify the title."
            f"{book_context}"
        )

        fiction_prompt = (
            "Choose a filename format for this fiction book. Use Book name_Author name "
            "for a standalone book or when the series and volume are unclear. Use "
            "Vol NNN_Series name_Book name_Author name for a numbered series. Write the "
            "volume as three digits, for example Vol 010 for volume 10. Use explicit "
            "volume evidence from the book or a filename of the form Series - 10 - Author. "
            "Preserve the book title and author names, and separate multiple authors with "
            "underscores. Keep titles and series names on one line without underscores. "
            "Use unknown for an unidentified book title or author. Return only the "
            "formatted name without a file extension."
            f"{book_context}"
        )

        name_prompt_paper = f"Identify the paper's full title from the first few pages, including any subtitle. Use the file name only as a hint. Preserve the original wording and language. Return only the title on one line.\nFile name: {file_name}\nFirst few pages:\n{txt}"

        name_prompt_document = f"Assign this document a proper title from the first few pages. Use the file name only as a hint. If the document has no explicit title, write a short title that describes its purpose or subject. Use the document's language and return only the title on one line. If the excerpt provides too little information to name the document, return unknown.\nFile name: {file_name}\nFirst few pages:\n{txt}"

        author_prompt_book = (
            "Return the author names credited for the whole book, in the order listed, "
            "with full names as printed. For an edited collection with no credited "
            "author, use its credited editors. Omit translators, foreword writers, and "
            "individual chapter contributors. Separate multiple names with underscores. "
            "Use the file name only as a hint. Return unknown if there is no clear credit."
            f"{book_context}"
        )

        author_prompt_paper = f"Identify the paper's authors from the first few pages. Use the file name only as a hint. Preserve the original spelling of the names. Return only the author names on one line, separated by underscores for multiple authors. If the authors cannot be determined, return unknown.\nFile name: {file_name}\nFirst few pages:\n{txt}"

        year_prompt_book = (
            "Find the publication year of this edition using the title or copyright "
            "page. Use the file name only as a hint. Return exactly one four-digit year, "
            "for example 2012, or unknown if this edition's year is unclear. "
            "Omit the book title, edition label, month, and all other text."
            f"{book_context}"
        )

        file_type = (self._ask(sort_prompt) or "").strip().lower()
        metadata = {
            "type": file_type,
            "name": "unknown",
            "author": "unknown",
            "year": "unknown",
        }

        match file_type:
            case "book":
                category = (self._ask(book_sort_prompt) or "").strip().lower()
                metadata["book_category"] = (
                    category
                    if category in {"fiction", "non fiction", "academic"}
                    else "unknown"
                )
                if category == "fiction":
                    metadata.update(_fiction_metadata(self._ask(fiction_prompt) or ""))
                    title = metadata["name"]
                else:
                    title = (self._ask(name_prompt_book) or "").strip()
                    metadata["name"] = book_title(title) or "unknown"
                    metadata["author"] = self._ask(author_prompt_book) or "unknown"
                metadata["year"] = (
                    publication_year(self._ask(year_prompt_book) or "", title)
                    or "unknown"
                )
            case "paper":
                metadata["name"] = self._ask(name_prompt_paper) or "unknown"
                metadata["author"] = self._ask(author_prompt_paper) or "unknown"
            case "document":
                metadata["name"] = self._ask(name_prompt_document) or "unknown"
            case _:
                metadata["type"] = "unknown"

        return metadata
