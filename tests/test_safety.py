from homeward import safety

PLAN = {"weight_gain_alert_lb": 3}


def test_emergency_phrases():
    assert safety.check("I have chest pain since lunch", PLAN)[0] == "emergency"
    assert safety.check("i cant breathe lying down", PLAN)[0] == "emergency"
    assert safety.check("My mom fainted in the kitchen", PLAN)[0] == "emergency"


def test_weight_gain_over_limit():
    assert safety.check("I'm up 4 pounds since yesterday", PLAN) [0] == "nurse"
    assert safety.check("gained 3 lbs overnight", PLAN)[0] == "nurse"
    assert safety.check("2 kg heavier this morning", PLAN)[0] == "nurse"


def test_weight_gain_under_limit_and_normal_text():
    assert safety.check("up 1 pound, feeling ok", PLAN) is None
    assert safety.check("Weight 150 lb today, took my pills", PLAN) is None
    assert safety.check("up 5 pounds", {}) is None  # no threshold in the letter, no rule
