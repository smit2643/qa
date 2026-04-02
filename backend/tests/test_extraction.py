"""Tests for Phase 4 Task 18: unified step normalizer."""

import pytest
from modules.extraction.normalizer import normalize_steps


# ---------------------------------------------------------------------------
# Basic normalization
# ---------------------------------------------------------------------------

def test_empty_input():
    assert normalize_steps([]) == []


def test_orders_are_sequential():
    steps = [
        {"order": 99, "action": "navigate", "selector": None, "value": "https://a.com", "description": "go"},
        {"order": 5,  "action": "click",    "selector": "Btn",  "value": None,           "description": "click it"},
    ]
    result = normalize_steps(steps)
    assert [s["order"] for s in result] == [0, 1]


def test_unknown_action_coerced_to_wait():
    steps = [{"order": 0, "action": "hover", "selector": "Menu", "value": None, "description": "hover menu"}]
    result = normalize_steps(steps)
    assert result[0]["action"] == "wait"


def test_valid_actions_preserved():
    for action in ("navigate", "click", "type", "assert", "wait"):
        steps = [{"order": 0, "action": action, "selector": None, "value": "x", "description": "d"}]
        result = normalize_steps(steps)
        assert result[0]["action"] == action


# ---------------------------------------------------------------------------
# Description filling
# ---------------------------------------------------------------------------

def test_missing_description_navigate():
    steps = [{"order": 0, "action": "navigate", "selector": None, "value": "https://example.com", "description": ""}]
    result = normalize_steps(steps)
    assert result[0]["description"] == "Navigate to https://example.com"


def test_missing_description_click():
    steps = [{"order": 0, "action": "click", "selector": "Login button", "value": None, "description": None}]
    result = normalize_steps(steps)
    assert result[0]["description"] == "Click Login button"


def test_missing_description_type():
    steps = [{"order": 0, "action": "type", "selector": "Email", "value": "x@y.com", "description": ""}]
    result = normalize_steps(steps)
    assert result[0]["description"] == "Type into Email"


def test_missing_description_fallback():
    steps = [{"order": 0, "action": "wait", "selector": None, "value": None, "description": ""}]
    result = normalize_steps(steps)
    assert result[0]["description"] == "Wait"


def test_existing_description_kept():
    steps = [{"order": 0, "action": "click", "selector": "Btn", "value": None, "description": "My custom description"}]
    result = normalize_steps(steps)
    assert result[0]["description"] == "My custom description"


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def test_consecutive_duplicates_removed():
    steps = [
        {"order": 0, "action": "click", "selector": "Login", "value": None, "description": "click"},
        {"order": 1, "action": "click", "selector": "Login", "value": None, "description": "click again"},
    ]
    result = normalize_steps(steps)
    assert len(result) == 1
    assert result[0]["order"] == 0


def test_non_consecutive_duplicates_kept():
    steps = [
        {"order": 0, "action": "click", "selector": "Btn", "value": None, "description": "first click"},
        {"order": 1, "action": "type",  "selector": "Field", "value": "hi", "description": "type"},
        {"order": 2, "action": "click", "selector": "Btn", "value": None, "description": "second click"},
    ]
    result = normalize_steps(steps)
    assert len(result) == 3


def test_multiple_consecutive_duplicates_collapsed():
    steps = [
        {"order": i, "action": "wait", "selector": None, "value": "1000", "description": "wait"}
        for i in range(5)
    ]
    result = normalize_steps(steps)
    assert len(result) == 1


# ---------------------------------------------------------------------------
# None / missing field tolerance
# ---------------------------------------------------------------------------

def test_missing_selector_and_value_become_none():
    steps = [{"order": 0, "action": "navigate", "description": "go somewhere"}]
    result = normalize_steps(steps)
    assert result[0]["selector"] is None
    assert result[0]["value"] is None


def test_missing_action_becomes_wait():
    steps = [{"order": 0, "selector": None, "value": None, "description": "something"}]
    result = normalize_steps(steps)
    assert result[0]["action"] == "wait"


# ---------------------------------------------------------------------------
# Full flow
# ---------------------------------------------------------------------------

def test_full_flow_normalizes_correctly():
    raw = [
        {"order": 5,  "action": "NAVIGATE", "selector": None,    "value": "https://app.com", "description": ""},
        {"order": 0,  "action": "click",     "selector": "Login", "value": None,              "description": ""},
        {"order": 0,  "action": "click",     "selector": "Login", "value": None,              "description": "dup"},
        {"order": 99, "action": "type",      "selector": "Email", "value": "u@t.com",         "description": "enter email"},
        {"order": 3,  "action": "bad_action","selector": None,    "value": None,              "description": "unknown"},
    ]
    result = normalize_steps(raw)
    # navigate (action uppercased should be lowercased), click, type, wait (bad_action → wait)
    # consecutive click dup removed
    assert len(result) == 4
    assert result[0]["action"] == "navigate"
    assert result[0]["description"] == "Navigate to https://app.com"
    assert result[1]["action"] == "click"
    assert result[1]["description"] == "Click Login"
    assert result[2]["action"] == "type"
    assert result[2]["description"] == "enter email"
    assert result[3]["action"] == "wait"
    assert [s["order"] for s in result] == [0, 1, 2, 3]
