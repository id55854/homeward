"""FastAPI app: nurse dashboard, stub phone, and the message loop.

Run: python -m uvicorn homeward.server:app --port 8030
"""
import logging
import threading
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import brain, config, safety, store
from .channel import Incoming, StubChannel, make_channel

log = logging.getLogger("homeward")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

STATIC = Path(__file__).parent / "static"
SAMPLES = config.ROOT / "samples"
channel = make_channel()
_work_lock = threading.Lock()  # one patient turn at a time keeps ordering simple

NOT_ENROLLED = (
    "Hi, this is Homeward, a follow-up line for patients who were just discharged. "
    "Your number is not on a care plan yet, so please ask your nurse to add you."
)
FALLBACK_REPLY = "Thanks for your message. I couldn't process it just now, so I've asked a nurse to call you."
HOLDING_TEXT = ("Hi, this is Homeward, the follow-up line from your care team. Your nurse is still checking "
                "your home plan. I'll text you as soon as it's ready. If you feel very unwell, call 911.")
FIRST_CONTACT = ("This is the start of the conversation. Reply with the plan's welcome message, then "
                 "today's key steps in two short sentences, then ask the first teach-back question.")
EMERGENCY_TEXT = ("Please call 911 now. What you described can be an emergency. "
                  "I have also alerted your nurse.")


# ---------------------------------------------------------------- message loop

def handle_incoming(msg: Incoming) -> None:
    if store.seen(msg.id):
        return
    patient = store.patient_by_handle(msg.handle)
    if patient is None:
        log.info("message from unknown sender %s", msg.handle)
        store.x("INSERT OR IGNORE INTO messages (patient_id, direction, text, photon_id, created_at) VALUES (0,'in',?,?,?)",
                (msg.text, msg.id, store.now()))
        channel.send(msg.space_id, msg.agent_user_id, NOT_ENROLLED, f"homeward-unknown:{msg.id}", msg.id)
        return

    pid = patient["id"]
    first_contact = not store.history(pid, 1)
    store.add_message(pid, "in", msg.text, msg.id)
    store.x("UPDATE patients SET space_id=?, agent_user_id=? WHERE id=?", (msg.space_id, msg.agent_user_id, pid))
    channel.typing(msg.space_id, msg.agent_user_id, True)

    # 1. Fixed rules first: they do not depend on the model.
    rule = safety.check(msg.text, patient["plan"], store.last_weight(pid))
    weights = safety.extract_weights(msg.text)
    if weights:
        store.add_weight(pid, weights[-1])  # most recent number in the text
    if rule:
        store.add_escalation(pid, rule[0], rule[1], "rule", msg.text)
    target = patient | {"space_id": msg.space_id, "agent_user_id": msg.agent_user_id}
    if rule and rule[0] == "emergency":
        # Fixed text goes out before any model call, so a slow or failed model cannot delay it.
        _send(target, EMERGENCY_TEXT, f"homeward-911:{msg.id}", msg.id)
        channel.typing(msg.space_id, msg.agent_user_id, True)

    # 2. Until the nurse approves the plan, the model does not coach from it.
    if not patient["approved"]:
        if not (rule and rule[0] == "emergency"):
            _send(target, HOLDING_TEXT, f"homeward-hold:{msg.id}", msg.id)
        return

    # 3. Model reply and triage.
    instruction = FIRST_CONTACT if first_contact else None
    try:
        turn = brain.respond(patient, store.history(pid), _teachback(pid), instruction)
        reply, level, reason = turn.reply, turn.escalate, turn.escalation_reason
        if turn.teach_back_question and turn.teach_back_correct is not None:
            store.add_teachback(pid, turn.teach_back_question, msg.text, turn.teach_back_correct)
    except Exception as exc:  # model down, refusal, bad output: fail towards a human
        log.exception("model call failed")
        reply, level, reason = FALLBACK_REPLY, "nurse", f"Model unavailable ({type(exc).__name__}); message needs a human"

    if level != "none" and not (rule and rule[0] == level):
        store.add_escalation(pid, level, reason or "Model flagged this message", "model", msg.text)
    _send(target, reply, f"homeward-reply:{msg.id}", msg.id)


def _send(patient: dict, text: str, key: str, parent_id: str | None = None) -> None:
    store.add_message(patient["id"], "out", text)
    try:
        channel.send(patient["space_id"], patient["agent_user_id"], text, key, parent_id)
    finally:
        channel.typing(patient["space_id"], patient["agent_user_id"], False)


def _teachback(pid: int) -> list[dict]:
    return store.q("SELECT question, correct FROM teachback WHERE patient_id=? ORDER BY id", (pid,))


def loop() -> None:
    log.info("message loop started on channel=%s", channel.name)
    while True:
        try:
            for msg in channel.poll():
                with _work_lock:
                    handle_incoming(msg)
        except Exception:
            log.exception("poll failed")
        time.sleep(config.POLL_SECONDS)


# ---------------------------------------------------------------- web app

app = FastAPI(title="Homeward")


@app.on_event("startup")
def _start() -> None:
    store.conn()
    threading.Thread(target=loop, daemon=True).start()


@app.get("/")
def dashboard():
    return FileResponse(STATIC / "dashboard.html")


@app.get("/phone")
def phone():
    return FileResponse(STATIC / "phone.html")


@app.get("/api/state")
def state():
    patients = store.patients()
    for p in patients:
        p["messages"] = store.history(p["id"], 200)
        p["escalations"] = store.q("SELECT * FROM escalations WHERE patient_id=? ORDER BY id DESC", (p["id"],))
        p["teachback"] = store.q("SELECT * FROM teachback WHERE patient_id=? ORDER BY id", (p["id"],))
        p["weights"] = store.q("SELECT lb, created_at FROM weights WHERE patient_id=? ORDER BY id", (p["id"],))
        p.pop("letter", None)
    return {
        "channel": channel.name,
        "agent_handle": config.PHOTON_AGENT_HANDLE,
        "model": config.MODEL,
        "patients": patients,
    }


class Enroll(BaseModel):
    name: str
    handle: str
    language: str = "English"
    letter: str


@app.post("/api/patients")
def enroll(body: Enroll):
    if not body.letter.strip():
        raise HTTPException(400, "Paste the discharge letter.")
    plan = brain.make_plan(body.letter, body.language)
    pid = store.add_patient(body.name, body.handle, body.language, body.letter, plan)
    return {"id": pid, "plan": plan}


@app.post("/api/patients/{pid}/approve")
def approve(pid: int):
    """Nurse signs off the extracted plan. If the patient already texted, send the welcome now."""
    if not store.patient(pid):
        raise HTTPException(404)
    store.x("UPDATE patients SET approved=1 WHERE id=?", (pid,))
    patient = store.patient(pid)
    sent = None
    if patient["space_id"]:
        with _work_lock:
            try:
                sent = brain.respond(patient, store.history(pid), _teachback(pid), FIRST_CONTACT).reply
            except Exception:
                log.exception("welcome failed")
                raise HTTPException(502, "Plan approved, but the welcome message failed; it will go out on the next text.")
            _send(patient, sent, f"homeward-welcome:{pid}")
    return {"approved": True, "sent": sent}


@app.post("/api/patients/{pid}/checkin")
def checkin(pid: int):
    """Advance to the next day and send that day's check-in (needs one earlier patient message)."""
    patient = store.patient(pid)
    if not patient:
        raise HTTPException(404)
    if not patient["approved"]:
        raise HTTPException(409, "Approve the plan first.")
    if not patient["space_id"]:
        raise HTTPException(409, "The patient has to text the line first; Photon shared lines cannot start a conversation.")
    with _work_lock:
        store.x("UPDATE patients SET day=day+1 WHERE id=?", (pid,))
        patient = store.patient(pid)
        try:
            turn = brain.respond(patient, store.history(pid), _teachback(pid),
                                 f"It is now the morning of day {patient['day']} at home. Send a short check-in: "
                                 "ask for today's numbers from the daily checks and how they feel, "
                                 "and remind them of anything due today. If a teach-back question is still open, ask one.")
            text = turn.reply
        except Exception:
            log.exception("check-in failed")
            raise HTTPException(502, "Model call failed")
        _send(patient, text, f"homeward-checkin:{pid}:{patient['day']}")
    return {"day": patient["day"], "text": text}


@app.post("/api/escalations/{eid}/ack")
def ack(eid: int):
    store.x("UPDATE escalations SET acknowledged=1 WHERE id=?", (eid,))
    return {"ok": True}


class StubText(BaseModel):
    handle: str
    text: str


@app.post("/stub/send")
def stub_send(body: StubText):
    if not isinstance(channel, StubChannel):
        raise HTTPException(409, "Running on Photon: text the real number instead.")
    channel.push(store.normalize_handle(body.handle), body.text)
    return {"ok": True}


@app.get("/api/samples")
def samples():
    return {p.stem: p.read_text(encoding="utf-8") for p in sorted(SAMPLES.glob("*.txt"))}
