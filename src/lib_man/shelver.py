import json
import re
import unicodedata
from collections.abc import Callable
from http.client import HTTPException
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class shelver:
    def __init__(
        self,
        path: str | Path,
        metadata: dict[str, Any],
        *,
        source: str | Path,
        ask: Callable[[str], str | None] | None = None,
    ) -> None:
        self.path = Path(path).expanduser()
        self.source = Path(source).expanduser()
        self.metadata = metadata
        self._ask = ask
        self.destination: Path | None = None
        if metadata["type"] == "book":
            self.book_shelver()
        elif metadata["type"] in {"paper", "document"}:
            self._shelve_document()

    def book_shelver(self) -> Path:
        """
        first check if exact mathch if found via online apis. if yes update metadata.

        if book is fiction:
            book name= (opt)series number and series name_book_name_author
            goes to path/fiction/ book_name
        if book is non fiction
            book name= book_name_series name
            goes to path/non-fiction/book_name
        if book is academic
            list all directories in path/STEM/
            for example if directories are path/STEM/math, path/STEM/optimization,....
            then categories are [unknown, math, optimization.....]
            send category list and book metadata to LLM <-ref to _ask in @metadata
            book name=book_name_author name_edition/year(optional)
            goes to path/STEM/<appropiate category>
            if unknown goes to path/STEM
        if book cat itself is unknown
            book_name=book_name_author_name
            goes to path/
        """
        if self.destination is not None:
            return self.destination
        if not self.source.is_file(follow_symlinks=False):
            raise ValueError(f"Book source must be a regular file: {self.source}")

        verified = _lookup_book(self.metadata)
        metadata = self.metadata | verified
        title = _text(metadata.get("name")) or self.source.stem
        author = _text(metadata.get("author"))
        series = _text(metadata.get("series"))
        number = _text(metadata.get("series_number"))
        category = " ".join(
            _text(metadata.get("book_category")).lower().replace("-", " ").split()
        )

        match category:
            case "fiction":
                directory = self.path / "fiction"
                series_prefix = (
                    " ".join(part for part in (number, series) if part)
                    if series
                    else ""
                )
                parts = (series_prefix, title, author)
            case "non fiction" | "nonfiction":
                directory = self.path / "non-fiction"
                parts = (title, series)
            case "academic":
                directory = self._academic_shelf(metadata)
                edition = _text(metadata.get("edition")) or _text(metadata.get("year"))
                parts = (title, author, edition)
            case _:
                directory = self.path
                parts = (title, author)

        stem = "_".join(part for part in map(_filename_part, parts) if part) or "book"
        self.destination = _move_file(self.source, directory, stem)
        self.metadata.update(verified)
        return self.destination

    def _shelve_document(self) -> None:
        title = _filename_part(_text(self.metadata.get("name"))) or self.source.stem
        author = (
            _filename_part(_text(self.metadata.get("author")))
            if self.metadata["type"] == "paper"
            else ""
        )
        stem = f"{title}_{author}" if author else title
        self.destination = _move_file(self.source, self.path, stem)

    def _academic_shelf(self, metadata: dict[str, Any]) -> Path:
        stem = self.path / "STEM"
        if self._ask is None or not stem.exists():
            return stem
        shelves = {
            entry.name: entry
            for entry in sorted(stem.iterdir())
            if entry.is_dir() and entry.name.casefold() != "unknown"
        }
        if not shelves:
            return stem

        choices = json.dumps(["unknown", *shelves], ensure_ascii=False)
        book = json.dumps(metadata, ensure_ascii=False, default=str)
        prompt = f"Choose the best existing academic shelf for this book. Return only one category exactly as listed. Choose unknown if no category fits.\nCategories: {choices}\nBook metadata: {book}"
        answer = (self._ask(prompt) or "").strip()
        if answer in shelves:
            return shelves[answer]
        matches = [
            shelf
            for name, shelf in shelves.items()
            if name.casefold() == answer.casefold()
        ]
        return matches[0] if len(matches) == 1 else stem


def _text(value: Any) -> str:
    text = str(value).strip() if isinstance(value, (str, int)) else ""
    return "" if text.casefold() == "unknown" else text


def _book_key(value: str) -> str:
    return " ".join(
        re.findall(r"[^\W_]+", unicodedata.normalize("NFKC", value).casefold())
    )


def _full_title(record: dict[str, Any]) -> str:
    return ": ".join(
        part
        for part in (_text(record.get("title")), _text(record.get("subtitle")))
        if part
    )


def _open_library(endpoint: str, **params: str) -> dict[str, Any]:
    url = f"https://openlibrary.org{endpoint}"
    if params:
        url = f"{url}?{urlencode(params)}"
    request = Request(
        url, headers={"Accept": "application/json", "User-Agent": "LibMan"}
    )
    try:
        with urlopen(request, timeout=5) as response:
            data = json.load(response)
    except OSError, HTTPException, ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _lookup_book(metadata: dict[str, Any]) -> dict[str, str]:
    title = _text(metadata.get("name"))
    authors = [
        name.strip()
        for name in _text(metadata.get("author")).split("_")
        if name.strip()
    ]
    if not title or not authors:
        return {}
    results = _open_library(
        "/search.json",
        title=title.partition(":")[0],
        author=authors[0],
        fields="key,title,subtitle,author_name",
        limit="20",
    )
    title_key = _book_key(title)
    author_keys = {_book_key(name) for name in authors}
    matches = [
        record
        for record in (results.get("docs") or [])
        if title_key
        in {_book_key(_text(record.get("title"))), _book_key(_full_title(record))}
        and author_keys
        == {_book_key(name) for name in (record.get("author_name") or [])}
    ]
    if len(matches) != 1:
        return {}
    work = matches[0]
    verified = {"name": _full_title(work), "author": "_".join(work["author_name"])}
    work_id = _text(work.get("key")).removeprefix("/works/")
    if re.fullmatch(r"OL\d+W", work_id):
        data = _open_library(f"/works/{work_id}/editions.json", limit="50")
        editions = data.get("entries") or []
        if data.get("size") == len(editions):
            year = re.search(r"\b\d{4}\b", _text(metadata.get("year")))
            exact_editions = [
                edition
                for edition in editions
                if title_key
                in {
                    _book_key(_text(edition.get("title"))),
                    _book_key(_full_title(edition)),
                }
                and (
                    year is None
                    or year[0]
                    in re.findall(r"\b\d{4}\b", _text(edition.get("publish_date")))
                )
            ]
            if len(exact_editions) == 1:
                verified.update(_edition_metadata(exact_editions[0]))
    return verified


def _edition_metadata(edition: dict[str, Any]) -> dict[str, str]:
    series = edition.get("series") or []
    series_name, _, series_number = _text(
        series[0] if len(series) == 1 else ""
    ).partition(";")
    year = re.search(r"\b\d{4}\b", _text(edition.get("publish_date")))
    fields = {
        "name": _full_title(edition),
        "edition": _text(edition.get("edition_name")),
        "year": year[0] if year else "",
        "series": series_name.strip(),
        "series_number": series_number.strip(" #") or _text(edition.get("volume")),
    }
    return {key: value for key, value in fields.items() if value}


def _filename_part(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", value)
    return " ".join(cleaned.split()).strip(" .")


def _move_file(source: Path, directory: Path, stem: str) -> Path:
    if not source.is_file(follow_symlinks=False):
        raise ValueError(f"Source must be a regular file: {source}")

    directory.mkdir(parents=True, exist_ok=True)
    directory = directory.resolve()
    source = source.parent.resolve() / source.name
    number = 1
    while True:
        suffix = source.suffix if number == 1 else f" ({number}){source.suffix}"
        # Leave room for both the extension and any collision suffix.
        budget = 255 - len(suffix.encode("utf-8"))
        name = (
            stem.encode("utf-8")[: max(0, budget)]
            .decode("utf-8", errors="ignore")
            .rstrip(" .")
        )
        destination = directory / f"{name}{suffix}"
        if destination == source:
            return source
        try:
            destination.touch(exist_ok=False)
        except FileExistsError:
            number += 1
            continue
        try:
            return source.move(destination)
        except OSError:
            destination.unlink(missing_ok=True)
            raise
