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
        else ["book", "Methods", "unknown", "2020", "academic"]
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
    assert failed.name in capsys.readouterr().err
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


@pytest.mark.parametrize("answers", [["unknown"], ["paper", "Title", "Author"]])
def test_main_leaves_unknown_and_unconfigured_types(configured_scan, answers):
    downloads, documents, _, response, sleep = configured_scan
    source = downloads / "source.txt"
    source.write_text("Test content.")
    response.side_effect = answers

    main.main()

    assert source.read_text() == "Test content."
    assert not documents.exists()
    assert response.call_count == len(answers)
    sleep.assert_not_called()


def test_main_requires_interactive_first_run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("builtins.input", Mock(side_effect=EOFError))

    with pytest.raises(SystemExit, match="Run the app interactively"):
        main.main()

    assert not (tmp_path / "file_config.json").exists()
