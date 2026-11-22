import io
import json
from pathlib import Path
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest

from lib_man import shelver


@pytest.mark.parametrize(
    ("category", "relative_path"),
    [
        ("fiction", "fiction/2 Example Series_Methods_Author.epub"),
        ("non-fiction", "non-fiction/Methods_Example Series.epub"),
        ("academic", "STEM/Math/Methods_Author_2nd edition.epub"),
        ("unknown", "Methods_Author.epub"),
    ],
)
def test_book_shelving_formats_and_routes_names(
    tmp_path, monkeypatch, category, relative_path
):
    source = tmp_path / "download.epub"
    source.write_bytes(b"contents")
    books = tmp_path / "Books"
    (books / "STEM" / "Math").mkdir(parents=True)
    (books / "STEM" / "unknown").mkdir()
    verify = Mock(return_value={"name": "Methods", "edition": "2nd edition"})
    monkeypatch.setattr(shelver, "_lookup_book", verify)
    ask = Mock(return_value=" math ")
    metadata = {
        "type": "book",
        "name": "Unverified title",
        "author": "Author",
        "book_category": category,
        "series": "Example Series",
        "series_number": 2,
        "year": "2021",
    }

    shelf = shelver.shelver(books, metadata, source=source, ask=ask)

    assert shelf.book_shelver() == shelf.destination == books / relative_path
    assert (books / relative_path).read_bytes() == b"contents"
    assert not source.exists()
    assert metadata["name"] == "Methods"
    verify.assert_called_once()
    if category == "academic":
        assert 'Categories: ["unknown", "Math"]' in ask.call_args.args[0]
    else:
        ask.assert_not_called()


def test_academic_book_with_unknown_category_goes_to_stem(tmp_path, monkeypatch):
    source = tmp_path / "download.epub"
    source.touch()
    books = tmp_path / "Books"
    (books / "STEM" / "Math").mkdir(parents=True)
    monkeypatch.setattr(shelver, "_lookup_book", Mock(return_value={}))
    metadata = {
        "type": "book",
        "name": "Methods",
        "book_category": "academic",
        "year": "2021",
    }

    shelf = shelver.shelver(
        books, metadata, source=source, ask=Mock(return_value="../Other")
    )

    assert shelf.destination == books / "STEM" / "Methods_2021.epub"


@pytest.mark.parametrize(
    ("kind", "title", "expected"),
    [
        ("paper", " Summary: Data / Results? ", "Summary Data Results_Author.pdf"),
        ("document", " Summary: Data / Results? ", "Summary Data Results.pdf"),
        ("document", " unknown ", "download.pdf"),
    ],
)
def test_document_and_paper_shelving(tmp_path, kind, title, expected):
    source = tmp_path / "download.pdf"
    source.write_text("example")
    directory = tmp_path / "Shelf"
    metadata = {"type": kind, "name": title, "author": "Author"}

    shelf = shelver.shelver(directory, metadata, source=source)

    assert shelf.destination == directory / expected
    assert (directory / expected).read_text() == "example"
    assert not source.exists()


def test_lookup_book_matches_normalized_title_authors_and_edition(monkeypatch):
    work = {
        "key": "/works/OL42W",
        "title": "The Methods",
        "subtitle": "Second Steps",
        "author_name": ["Alice", "Bob"],
    }
    edition = {
        "title": "The Methods",
        "subtitle": "Second Steps",
        "edition_name": "Revised",
        "publish_date": "May 2020",
        "series": ["Math Essentials; #4"],
    }
    responses = [
        {"docs": [work, work | {"author_name": ["Charlie"]}]},
        {"size": 2, "entries": [edition, edition | {"publish_date": "2001"}]},
    ]
    open_url = Mock(
        side_effect=[io.BytesIO(json.dumps(body).encode()) for body in responses]
    )
    monkeypatch.setattr(shelver, "urlopen", open_url)
    metadata = {
        "name": "ＴHE Methods: Second Steps",
        "author": "bob_Alice",
        "year": "2020",
    }

    assert shelver._lookup_book(metadata) == {
        "name": "The Methods: Second Steps",
        "author": "Alice_Bob",
        "edition": "Revised",
        "year": "2020",
        "series": "Math Essentials",
        "series_number": "4",
    }
    request = open_url.call_args_list[0].args[0]
    search = urlsplit(request.full_url)
    assert search.netloc == "openlibrary.org"
    assert search.path == "/search.json"
    assert parse_qs(search.query)["title"] == ["ＴHE Methods"]
    assert parse_qs(search.query)["author"] == ["bob"]
    assert request.get_header("Accept") == "application/json"
    edition_request = open_url.call_args_list[1].args[0]
    assert urlsplit(edition_request.full_url).path == "/works/OL42W/editions.json"
    assert open_url.call_args.kwargs["timeout"] == 5


def test_lookup_book_leaves_ambiguous_results_unverified(monkeypatch):
    match = {"title": "Methods", "author_name": ["Author"]}
    library = Mock(return_value={"docs": [match, match]})
    monkeypatch.setattr(shelver, "_open_library", library)

    assert shelver._lookup_book({"name": "Methods", "author": "Author"}) == {}
    library.assert_called_once()


@pytest.mark.parametrize("body", [b"[]", b"invalid JSON"])
def test_open_library_ignores_unusable_responses(monkeypatch, body):
    monkeypatch.setattr(shelver, "urlopen", Mock(return_value=io.BytesIO(body)))

    assert shelver._open_library("/search.json") == {}


def test_open_library_handles_network_errors(monkeypatch):
    monkeypatch.setattr(shelver, "urlopen", Mock(side_effect=TimeoutError))

    assert shelver._open_library("/search.json") == {}


def test_move_file_avoids_overwrite_and_trims_utf8_names(tmp_path):
    directory = tmp_path / "Shelf"
    directory.mkdir()
    existing = directory / ("é" * 125 + ".pdf")
    existing.write_text("first")
    source = tmp_path / "download.pdf"
    source.write_text("second")

    destination = shelver._move_file(source, directory, "é" * 150)

    assert existing.read_text() == "first"
    assert destination.read_text() == "second"
    assert destination.name == "é" * 123 + " (2).pdf"
    assert not source.exists()
    assert shelver._move_file(destination, directory, destination.stem) == destination


def test_move_file_cleans_up_destination_on_failure(tmp_path, monkeypatch):
    source = tmp_path / "source.pdf"
    source.write_text("contents")
    directory = tmp_path / "Shelf"
    monkeypatch.setattr(Path, "move", Mock(side_effect=OSError("move failed")))

    with pytest.raises(OSError, match="move failed"):
        shelver._move_file(source, directory, "Title")

    assert source.read_text() == "contents"
    assert list(directory.iterdir()) == []
