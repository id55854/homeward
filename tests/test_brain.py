from homeward import brain

PATIENT = {"name": "Maria", "language": "English", "day": 1, "plan": {}}


def capture(monkeypatch):
    seen = {}
    monkeypatch.setattr(brain, "_call", lambda cls, system, messages, effort, timeout=20.0: seen.setdefault("m", messages))
    return seen


def test_last_turn_is_user_after_automatic_911_text(monkeypatch):
    seen = capture(monkeypatch)
    history = [{"direction": "in", "text": "tengo dolor de pecho"},
               {"direction": "out", "text": "Please call 911 now."}]
    brain.respond(PATIENT, history, [])
    assert seen["m"][-1]["role"] == "user"


def test_roles_alternate(monkeypatch):
    seen = capture(monkeypatch)
    history = [{"direction": "in", "text": "a"}, {"direction": "in", "text": "b"},
               {"direction": "out", "text": "c"}, {"direction": "in", "text": "d"}]
    brain.respond(PATIENT, history, [])
    roles = [m["role"] for m in seen["m"]]
    assert all(x != y for x, y in zip(roles, roles[1:])) and roles[-1] == "user"
