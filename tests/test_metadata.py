"""Metadata normalization."""

from __future__ import annotations

import json

from orqestra.capabilities.kb_core import _normalize_metadata


def test_normalize_dict():
    d = {"title": "T", "tags": ["a"]}
    assert _normalize_metadata(d) == d


def test_normalize_json_string():
    s = json.dumps({"title": "X", "category": "topics"})
    r = _normalize_metadata(s)
    assert r["title"] == "X"
    assert r["category"] == "topics"


def test_normalize_none():
    assert _normalize_metadata(None) == {}


def test_normalize_empty_string():
    assert _normalize_metadata("") == {}


def test_normalize_integer():
    r = _normalize_metadata(42)
    assert r == {}


def test_normalize_nested():
    d = {"outer": {"inner": 1}}
    r = _normalize_metadata(d)
    assert r["outer"]["inner"] == 1
