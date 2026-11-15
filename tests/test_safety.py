import pytest

from homeward import safety

PLAN = {"weight_gain_alert_lb": 3, "weight_gain_week_lb": 5}


def level(text, plan=PLAN, previous=None):
    hit = safety.check(text, plan, previous)
    return hit[0] if hit else None


@pytest.mark.parametrize("text", [
    "I have chest pain since lunch",
    "i cant breathe lying down",
    "My mom fainted in the kitchen",
    "I feel confused and don't know what day it is",
    "very short of breath sitting still",
    "tengo dolor de pecho",
    "no puedo respirar",
    "me desmayé esta mañana",
])
def test_emergency(text):
    assert level(text) == "emergency"


@pytest.mark.parametrize("text", [
    "cant catch my breath walking to the mailbox",
    "my ankles look bigger",
    "had to use more pillows last night",
    "a bit dizzy when I stand up",
    "tengo los pies hinchados",
    "me falta el aire al caminar",
])
def test_call_nurse(text):
    assert level(text) == "nurse"


@pytest.mark.parametrize("text", [
    "no chest pain today",
    "I did not pass out",
    "not short of breath, feeling good",
    "no dolor de pecho hoy",
    "Weight 150 lb today, took my pills",
    "up 1 pound, feeling ok",
])
def test_no_alert(text):
    assert level(text) is None


def test_negation_is_per_clause():
    assert level("no chest pain but my legs are swollen") == "nurse"


@pytest.mark.parametrize("text", [
    "I'm up 4 pounds since yesterday",
    "gained 3 lbs overnight",
    "2 kg heavier this morning",
    "weighed 150 yesterday, 154 today",
    "subí 4 libras",
])
def test_daily_weight_gain(text):
    assert level(text) == "nurse"


def test_weekly_limit():
    assert level("up 4 lb this week") is None      # under the 5 lb weekly limit
    assert level("gained 5 lb this week") == "nurse"
    assert level("weighed 150 last week, 156 now") == "nurse"


def test_default_limit_when_letter_has_none():
    hit = safety.check("up 4 pounds", {})
    assert hit[0] == "nurse" and "default" in hit[1]


def test_compares_with_previous_reported_weight():
    assert level("154 this morning", previous=150.0) == "nurse"
    assert level("151 this morning", previous=150.0) is None


def test_extract_weights():
    assert safety.extract_weights("weighed 150 yesterday, 154 today") == [150.0, 154.0]
    assert safety.extract_weights("took 2 pills at 8") == []
