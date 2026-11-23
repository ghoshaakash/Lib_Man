from unittest.mock import Mock, call

import pytest

from lib_man import metadata


@pytest.fixture
def mocked_lookup(monkeypatch):
    calls = Mock()
    make_llm = Mock(return_value=calls.provider)
    monkeypatch.setattr(metadata, "LLMGen", make_llm)
    monkeypatch.setattr(metadata, "sleep", calls.sleep)
    lookup = metadata.metadataLookup("google")
    make_llm.assert_called_once_with("google")
    return lookup, calls


@pytest.mark.parametrize("failures", [0, 1, 2])
def test_ask_stops_at_first_success(mocked_lookup, failures):
    lookup, calls = mocked_lookup
    calls.provider.response.side_effect = [OSError("unavailable")] * failures + ["ok"]

    assert lookup._ask("prompt") == "ok"
    first_attempt = call.provider.response("prompt")
    retry = [call.sleep(10), call.provider.response("prompt")]
    assert calls.mock_calls == [first_attempt, *retry * failures]


def test_ask_gives_up_after_two_retries(mocked_lookup):
    lookup, calls = mocked_lookup
    last_error = OSError("last failure")
    calls.provider.response.side_effect = [OSError(), OSError(), last_error]

    with pytest.raises(metadata.PromptAttemptsExhausted) as caught:
        lookup._ask("prompt")

    assert caught.value.__cause__ is last_error
    assert calls.mock_calls == [
        call.provider.response("prompt"),
        call.sleep(10),
        call.provider.response("prompt"),
        call.sleep(10),
        call.provider.response("prompt"),
    ]


@pytest.mark.parametrize(
    ("answers", "expected"),
    [
        (
            [" BOOK ", " Academic ", "Book title", "A_B", "2020"],
            {
                "type": "book",
                "name": "Book title",
                "author": "A_B",
                "year": "2020",
                "book_category": "academic",
            },
        ),
        (
            ["book", "unrecognized", None, None, None],
            {
                "type": "book",
                "name": "unknown",
                "author": "unknown",
                "year": "unknown",
                "book_category": "unknown",
            },
        ),
        (
            ["book", "fiction", "Novel\nSubtitle_Alice_Bob", "2021"],
            {
                "type": "book",
                "name": "Novel Subtitle",
                "author": "Alice_Bob",
                "year": "2021",
                "book_category": "fiction",
            },
        ),
        (
            ["paper", "Paper title", "A"],
            {"type": "paper", "name": "Paper title", "author": "A", "year": "unknown"},
        ),
        (
            ["document", "Document title"],
            {
                "type": "document",
                "name": "Document title",
                "author": "unknown",
                "year": "unknown",
            },
        ),
        (
            ["unexpected"],
            {
                "type": "unknown",
                "name": "unknown",
                "author": "unknown",
                "year": "unknown",
            },
        ),
    ],
    ids=[
        "book",
        "missing-book-fields",
        "standalone-fiction",
        "paper",
        "document",
        "unknown",
    ],
)
def test_get_metadata(mocked_lookup, answers, expected):
    lookup, calls = mocked_lookup
    calls.provider.response.side_effect = answers

    assert lookup.get_metadata("file-name", "first-page text") == expected
    assert calls.provider.response.call_count == len(answers)
    for request in calls.provider.response.call_args_list:
        assert (
            "File name: file-name\nFirst few pages:\nfirst-page text" in request.args[0]
        )
    calls.sleep.assert_not_called()


@pytest.mark.parametrize(
    ("title", "reply", "expected_title", "expected_year"),
    [
        ("A Study of 1900", "A Study of 1900 (2012)", "A Study of 1900", "2012"),
        ("A Study of 1900", "A Study of 1900", "A Study of 1900", "unknown"),
        ("Methods", "First published August\u00a02025.", "Methods", "2025"),
        ("Methods", "2018-05-10", "Methods", "2018"),
        ("Methods", "Copyright 2006; revised 2020", "Methods", "unknown"),
        ("Methods", "ISBN 978-1-4471-2158-9", "Methods", "unknown"),
        ("Methods — Fourth Edition", "Fourth edition, 2013", "Methods", "2013"),
    ],
)
def test_book_metadata_cleans_title_and_year(
    mocked_lookup, title, reply, expected_title, expected_year
):
    lookup, calls = mocked_lookup
    calls.provider.response.side_effect = ["book", "academic", title, "Author", reply]

    result = lookup.get_metadata("download", "first-page text")

    assert result["name"] == expected_title
    assert result["year"] == expected_year
