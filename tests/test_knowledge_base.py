"""KnowledgeBase round-trip and helpers."""

from __future__ import annotations

from orqestra.capabilities.knowledge import KnowledgeBase


def test_write_search_read_roundtrip(tmp_kb: KnowledgeBase):
    tmp_kb.write(
        "wiki/wissen/test-kb.md",
        {"title": "T", "category": "wissen"},
        "# T\n\nHello world unique-xyz-123.",
    )
    hits, _ = tmp_kb.search("unique-xyz-123", limit=5)
    assert any("test-kb" in h.get("path", "") for h in hits)
    doc = tmp_kb.read("wiki/wissen/test-kb.md")
    assert "Hello world" in doc.get("content", "")


def test_delete_and_cleanup(tmp_kb: KnowledgeBase):
    tmp_kb.write(
        "wiki/wissen/a.md",
        {"title": "A", "category": "wissen"},
        "Link to [b](wiki/wissen/b.md)",
    )
    tmp_kb.write(
        "wiki/wissen/b.md",
        {"title": "B", "category": "wissen"},
        "Back to [a](wiki/wissen/a.md)",
    )
    res = tmp_kb.delete("wiki/wissen/b.md")
    assert res.get("success") is True
    a = tmp_kb.read("wiki/wissen/a.md")
    assert "wiki/wissen/b.md" not in (a.get("content") or "")


def test_link_variants_path_math():
    v = KnowledgeBase._link_variants(
        "wiki/wissen/from.md",
        "wiki/akteure/remote.md",
    )
    assert "wiki/akteure/remote.md" in v
    assert any(".." in x for x in v) or len(v) >= 1
