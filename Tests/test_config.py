import pytest

from lib_man.config import GetKey


def test_groq_key(monkeypatch):
    monkeypatch.setenv("GROQ_KEY", "test-groq-key")

    config = GetKey(provider="groq")

    assert config.key == "test-groq-key"


def test_gemini_key(monkeypatch):
    monkeypatch.setenv("GEMINI_KEY", "test-gemini-key")

    config = GetKey(provider="google")

    assert config.key == "test-gemini-key"


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
