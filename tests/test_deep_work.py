"""Tests for deep-work eval JSON parsing."""

from __future__ import annotations

import json

from orqestra.core.deep_work import _parse_eval_result


def test_parse_eval_think_tags_stripped():
    inner = json.dumps({
        "status": "GOAL_REACHED",
        "progress_pct": 100,
        "summary": "done",
        "next_step": "",
    })
    text = ("<" + "think" + ">reasoning here</" + "think" + ">\n") + inner
    r = _parse_eval_result(text)
    assert r["status"] == "GOAL_REACHED"
    assert r["progress_pct"] == 100


def test_parse_eval_valid_json_goal_reached():
    text = json.dumps({
        "status": "GOAL_REACHED",
        "progress_pct": 100,
        "summary": "done",
        "next_step": "",
    })
    r = _parse_eval_result(text)
    assert r["status"] == "GOAL_REACHED"
    assert r["progress_pct"] == 100
    assert r["summary"] == "done"


def test_parse_eval_valid_json_continue():
    text = json.dumps({
        "status": "CONTINUE",
        "progress_pct": 42,
        "summary": "halfway",
        "next_step": "write more",
    })
    r = _parse_eval_result(text)
    assert r["status"] == "CONTINUE"
    assert r["progress_pct"] == 42
    assert r["next_step"] == "write more"


def test_parse_eval_json_in_markdown_fence():
    inner = json.dumps({
        "status": "CONTINUE",
        "progress_pct": 10,
        "summary": "x",
        "next_step": "y",
    })
    text = f"```json\n{inner}\n```"
    r = _parse_eval_result(text)
    assert r["status"] == "CONTINUE"
    assert r["progress_pct"] == 10


def test_parse_eval_broken_json():
    r = _parse_eval_result("{not json")
    assert r["status"] == "CONTINUE"
    assert r["progress_pct"] == 0


def test_parse_eval_goal_reached_substring():
    r = _parse_eval_result("Some noise GOAL_REACHED in text")
    assert r["status"] == "GOAL_REACHED"
    assert r["progress_pct"] == 100


def test_parse_eval_empty_string():
    r = _parse_eval_result("")
    assert r["status"] == "CONTINUE"
