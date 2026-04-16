"""FTS query helpers."""

from __future__ import annotations

from orqestra.capabilities.kb_core import (
    _build_fts_or_query,
    _fts5_prefix_term,
    _tokenize_search_query,
)


def test_tokenize_stopwords_and_punctuation():
    toks = _tokenize_search_query("the und Autowerkstätten")
    assert "the" not in toks
    assert "und" not in toks
    assert "Autowerkstätten" in toks


def test_tokenize_single_token():
    assert _tokenize_search_query("hello") == ["hello"]


def test_tokenize_empty():
    assert _tokenize_search_query("") == []
    assert _tokenize_search_query("   ") == []


def test_fts5_prefix_normal_word():
    t = _fts5_prefix_term("hello")
    assert "hello" in t or t.startswith("hello")


def test_fts5_prefix_special_chars():
    _fts5_prefix_term("test@#$")
    # should not raise


def test_fts5_prefix_empty():
    assert _fts5_prefix_term("") == ""


def test_build_fts_or_multiple():
    q = _build_fts_or_query(["a", "b", "c"])
    assert "OR" in q or "a" in q


def test_build_fts_or_single():
    q = _build_fts_or_query(["only"])
    assert "only" in q


def test_build_fts_or_empty():
    assert _build_fts_or_query([]) == ""
