import json

import pytest

from lib_man.config import GetKey, get_file_configs, set_file_cofigs


def test_groq_key(monkeypatch):
    monkeypatch.setenv("GROQ_KEY", "test-groq-key")

    config = GetKey(provider="groq")

    assert config.get_llm_key() == "test-groq-key"


def test_gemini_key(monkeypatch):
    monkeypatch.setenv("GEMINI_KEY", "test-gemini-key")

    config = GetKey(provider="google")

    assert config.get_llm_key() == "test-gemini-key"


def test_missing_groq_key(monkeypatch):
    monkeypatch.delenv("GROQ_KEY", raising=False)

    with pytest.raises(RuntimeError):
        GetKey(provider="groq")


def test_missing_gemini_key(monkeypatch):
    monkeypatch.delenv("GEMINI_KEY", raising=False)

    with pytest.raises(RuntimeError):
        GetKey(provider="google")


def test_unsupported_provider():
    with pytest.raises(RuntimeError):
        GetKey(provider="unsupported")


@pytest.mark.parametrize(
    "use_default_directory", [True, False], ids=["default", "explicit"]
)
@pytest.mark.parametrize(
    ("book_input", "expected_book_path"),
    [
        ("  Bibliothèque, Books  ", "Bibliothèque, Books"),
        ("   ", ""),
    ],
    ids=["single-path", "blank"],
)
def test_set_file_configs(
    tmp_path, monkeypatch, use_default_directory, book_input, expected_book_path
):
    monkeypatch.chdir(tmp_path)
    base_path = None if use_default_directory else tmp_path / "library"
    config_dir = base_path or tmp_path
    config_dir.mkdir(exist_ok=True)
    answers = iter(["groq", "Documents", "Papers", book_input])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))

    set_file_cofigs(base_path)

    config_file = config_dir / "file_config.json"
    assert json.loads(config_file.read_text(encoding="utf-8")) == {
        "provider": "groq",
        "doc_path": "Documents",
        "paper_path": "Papers",
        "book_path": expected_book_path,
    }


@pytest.mark.parametrize(
    "use_default_directory", [True, False], ids=["default", "explicit"]
)
def test_get_file_configs(tmp_path, monkeypatch, use_default_directory):
    monkeypatch.chdir(tmp_path)
    base_path = None if use_default_directory else tmp_path / "library"
    config_dir = base_path or tmp_path
    config_dir.mkdir(exist_ok=True)
    expected = {
        "provider": "google",
        "doc_path": "Documents",
        "paper_path": "Papers",
        "book_path": "Bibliothèque",
    }
    (config_dir / "file_config.json").write_text(
        json.dumps(expected, ensure_ascii=False), encoding="utf-8"
    )

    assert get_file_configs(base_path) == expected


def test_first_run_creates_and_reuses_config(tmp_path, monkeypatch):
    from lib_man import main

    monkeypatch.chdir(tmp_path)
    answers = iter(["unsupported", " GOOGLE ", "Documents", "", "Books"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))
    providers = []
    monkeypatch.setattr(
        main, "metadataLookup", lambda provider: providers.append(provider)
    )

    main.main()
    main.main()

    assert providers == ["google", "google"]
    assert get_file_configs() == {
        "provider": "google",
        "doc_path": "Documents",
        "paper_path": "",
        "book_path": "Books",
    }
