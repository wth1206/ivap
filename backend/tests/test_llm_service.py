"""LLM JSON parsing tests (no network)."""

import pytest
from app.services.llm_service import extract_json


def test_extract_plain_json():
    assert extract_json('{"a": 1, "b": "x"}') == {"a": 1, "b": "x"}


def test_extract_json_code_fence():
    text = '```json\n{"ok": true, "name": "ivap"}\n```'
    assert extract_json(text) == {"ok": True, "name": "ivap"}


def test_extract_json_with_leading_text():
    text = 'Here is the result:\n{"total": 33}\nDone.'
    assert extract_json(text) == {"total": 33}


def test_extract_json_invalid():
    with pytest.raises(ValueError):
        extract_json("not json at all")
    with pytest.raises(ValueError):
        extract_json("")
