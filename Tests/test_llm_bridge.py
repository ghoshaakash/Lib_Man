import os
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from lib_man import llm_bridge


def test_groq_response(monkeypatch):
    monkeypatch.setenv("GROQ_KEY", "test-groq-key")
    groq = Mock()
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Hello world"))]
    )
    groq.return_value.chat.completions.create.return_value = response
    monkeypatch.setattr(llm_bridge, "Groq", groq)

    llm = llm_bridge.LLMGen()

    groq.assert_called_once_with(api_key="test-groq-key")
    assert llm.response("Say hello") == "Hello world"
    groq.assert_called_with(api_key="test-groq-key", max_retries=0)
    groq.return_value.chat.completions.create.assert_called_once_with(
        messages=[{"role": "user", "content": "Say hello"}],
        model="openai/gpt-oss-120b",
    )


def test_gemini_response(monkeypatch):
    monkeypatch.setenv("GEMINI_KEY", "test-gemini-key")
    gemini = Mock()
    gemini.return_value.interactions.create.return_value = SimpleNamespace(
        output_text="Hello world"
    )
    monkeypatch.setattr(llm_bridge.genai, "Client", gemini)

    llm = llm_bridge.LLMGen("google")

    gemini.assert_called_once_with(api_key="test-gemini-key")
    assert llm.response("Say hello") == "Hello world"
    options = gemini.call_args.kwargs["http_options"]
    assert options.retry_options.attempts == 1
    assert options.timeout is None
    gemini.return_value.interactions.create.assert_called_once_with(
        model="gemini-4-hydrogen", input="Say hello"
    )


@pytest.mark.skipif(
    os.getenv("LIB_MAN_LIVE_LLM_TESTS") != "1",
    reason="Set LIB_MAN_LIVE_LLM_TESTS=1 to run live tests.",
)
@pytest.mark.parametrize(
    ("provider", "key_name"), [("groq", "GROQ_KEY"), ("google", "GEMINI_KEY")]
)
def test_live_llm_response(provider, key_name):
    if not os.getenv(key_name):
        pytest.skip(f"{key_name} is missing.")

    response = llm_bridge.LLMGen(provider).response('Reply with only "Hello world".')
    assert response and response.strip()
