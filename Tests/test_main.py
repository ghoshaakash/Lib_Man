import json
from unittest.mock import Mock, call

import pytest

from lib_man import main, metadata


@pytest.fixture
def configured_scan(tmp_path, monkeypatch):
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    documents = tmp_path / "Documents"
    books = tmp_path / "Books"
    (books / "STEM" / "Math").mkdir(parents=True)
    (downloads / "file_config.json").write_text(
        json.dumps(
            {"provider": "groq", "doc_path": str(documents), "book_path": str(books)}
        )
    )
    monkeypatch.chdir(downloads)
    response = Mock()
    monkeypatch.setattr(metadata, "LLMGen", Mock(return_value=Mock(response=response)))
    sleep = Mock()
    monkeypatch.setattr(metadata, "sleep", sleep)
    return downloads, documents, books, response, sleep


@pytest.mark.parametrize("stage", ["classification", "academic shelf"])
def test_model_failure_skips_file_and_continues(configured_scan, capsys, stage):
    downloads, documents, books, response, sleep = configured_scan
    failed = downloads / "01-failed.txt"
    failed.write_bytes(b"Original file contents.")
    good = downloads / "02-notes.txt"
    good.write_text("Text the model should receive.")
    answers = (
        []
        if stage == "classification"
        else ["book", "academic", "Methods", "unknown", "2020"]
    )
    response.side_effect = [
        *answers,
        OSError("unavailable"),
        OSError("unavailable"),
        OSError("unavailable"),
        "document",
        "Sorted notes",
    ]

    main.main()

    assert failed.read_bytes() == b"Original file contents."
    assert not list(books.rglob("*.txt"))
    assert not good.exists()
    assert (
        documents / "Sorted notes.txt"
    ).read_text() == "Text the model should receive."
    log = downloads / "lib_man.log"
    entry = (
        f"Moved\n  From  {good.name}\n  To    {documents / 'Sorted notes.txt'}\n"
        '  Metadata\n    {\n      "type": "document",\n      "name": "Sorted notes",\n'
        '      "author": "unknown",\n      "year": "unknown"\n    }\n\n'
    )
    assert log.read_text(encoding="utf-8") == entry
    output = capsys.readouterr()
    assert failed.name in output.err
    assert f"[1/2] {failed.name}\n  Reading the first pages..." in output.out
    assert f"[2/2] {good.name}" in output.out
    assert entry.rstrip() in output.out
    assert "Scan complete. 1 moved, 1 skipped." in output.out
    assert sleep.call_args_list == [call(10), call(10)]
    assert response.call_count == len(answers) + 5
    failed_prompt = response.call_args_list[len(answers)].args[0]
    if stage == "academic shelf":
        assert 'Categories: ["unknown", "Math"]' in failed_prompt
    else:
        assert "Original file contents." in failed_prompt
    assert "Text the model should receive." in response.call_args.args[0]

    response.reset_mock()
    main.main()

    response.assert_not_called()
    assert json.loads((downloads / "lib_man.json").read_text()) == [failed.name]
    assert log.read_text(encoding="utf-8") == entry
    assert "No new files." in capsys.readouterr().out


@pytest.mark.parametrize(
    ("answers", "reason"),
    [
        (["unknown"], "File type could not be identified."),
        (["paper", "Title", "Author"], "No paper shelf is configured."),
    ],
)
def test_main_leaves_unknown_and_unconfigured_types(
    configured_scan, capsys, answers, reason
):
    downloads, documents, _, response, sleep = configured_scan
    source = downloads / "source.txt"
    source.write_text("Test content.")
    response.side_effect = answers

    main.main()

    assert source.read_text() == "Test content."
    assert not documents.exists()
    assert not (downloads / "lib_man.log").exists()
    assert response.call_count == len(answers)
    sleep.assert_not_called()
    assert reason in capsys.readouterr().out


def test_main_requires_interactive_first_run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("builtins.input", Mock(side_effect=EOFError))

    with pytest.raises(SystemExit, match="Run the app interactively"):
        main.main()

    assert not (tmp_path / "file_config.json").exists()


def test_destination_collision_warns_and_scan_continues(configured_scan, capsys):
    downloads, documents, _, response, _ = configured_scan
    documents.mkdir()
    existing = documents / "Notes.txt"
    existing.write_text("Previously shelved")
    incoming = downloads / "01-incoming.txt"
    incoming.write_text("Incoming copy")
    next_file = downloads / "02-other.txt"
    next_file.write_text("Other content")
    response.side_effect = ["document", "Notes", "document", "Other"]

    main.main()

    output = capsys.readouterr()
    assert (
        f"Warning: {existing} already exists. Left {incoming.name} in place."
        in output.err
    )
    assert "Scan complete. 1 moved, 1 skipped." in output.out
    assert existing.read_text() == "Previously shelved"
    assert incoming.read_text() == "Incoming copy"
    assert sorted(path.name for path in documents.iterdir()) == [
        "Notes.txt",
        "Other.txt",
    ]
    assert (documents / "Other.txt").read_text() == "Other content"
    assert incoming.name not in (downloads / "lib_man.log").read_text()


def test_programming_guide_uses_academic_filename(configured_scan, monkeypatch):
    downloads, _, books, response, _ = configured_scan
    (books / "Engineering").mkdir()
    title = "Build a Large Language Model (From Scratch)"
    source = downloads / "Build a Large Language Model (from Scratch).pdf"
    source.touch()
    monkeypatch.setattr(
        main, "ocr", Mock(return_value="Code and train a language model.")
    )
    monkeypatch.setattr("lib_man.shelver._lookup_book", Mock(return_value={}))
    response.side_effect = [
        "book",
        "academic",
        title,
        "Sebastian Raschka",
        "2024",
        "unknown",
    ]

    main.main()

    destination = books / "STEM" / f"{title}_Sebastian Raschka_2024.pdf"
    assert destination.is_file()
    assert not source.exists()
    prompts = [request.args[0] for request in response.call_args_list]
    assert "training a language model from scratch is academic" in prompts[1]
    assert "capitalization, and parentheses" in prompts[2]
    assert 'Categories: ["unknown", "Math"]' in prompts[5]


def test_fiction_volumes_keep_source_numbers(configured_scan, monkeypatch):
    downloads, _, books, response, _ = configured_scan
    title = "Dahlia in Bloom Crafting a Fresh Start with Magical Tools"
    series = "Dahlia in Bloom"
    author = "Hisaya Amagishi"
    monkeypatch.setattr(main, "ocr", Mock(return_value="Opening pages."))
    monkeypatch.setattr("lib_man.shelver._lookup_book", Mock(return_value={}))
    for number in (10, 11):
        (downloads / f"{series} (Light Novels) - {number} - {author}.epub").write_text(
            str(number)
        )
    response.side_effect = [
        "book",
        "fiction",
        f"Vol 010_{series}_{title}_{author}",
        "unknown",
        "book",
        "fiction",
        f"{title}_{author}",
        "unknown",
    ]

    main.main()

    first = books / "fiction" / f"Vol 010_{series} (Light Novels)_{title}_{author}.epub"
    second = (
        books / "fiction" / f"Vol 011_{series} (Light Novels)_{title}_{author}.epub"
    )
    assert first.read_text() == "10"
    assert second.read_text() == "11"
