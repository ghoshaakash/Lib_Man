import pytest

from lib_man.llm_bridge import LLMGen


@pytest.mark.parametrize("provider", ["groq", "google"])
def test_llm_bridge_response(provider):
    prompt = 'reply with this exact sting only: "Hello world"'

    assert LLMGen(provider).response(prompt) == "Hello world"
