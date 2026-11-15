# Homeward

A text-message companion for the first weeks after a hospital stay. Built at HackPrinceton Fall 2026 for the
**Photon: Build a Messaging Agent using Photon 2.0** track.

About 1 in 5 Medicare patients who leave hospital is back within 30 days (Jencks et al., NEJM 2009, 19.6%).
Many of those patients went home with a discharge letter they could not fully read, and a warning sign
(a few pounds of water weight, a pill taken with the one it replaced) that nobody heard about in time.

Homeward does three things over iMessage:

1. **Turns the discharge letter into a plan.** A nurse pastes the letter into the dashboard. Claude extracts
   the medications (new, changed, stopped), daily checks, "call 911 if", "call the nurse if", weight limits,
   follow-up dates and three teach-back questions, written for a 5th-grade reader in the patient's language.
   The plan is a draft until the nurse approves it; before that the patient only gets a holding message.
2. **Checks understanding by text.** The agent asks the teach-back questions one at a time and records
   whether each answer covered the key points. The nurse sees which ones need review.
3. **Escalates red flags to a person.** Every patient message goes through fixed rules first (English and
   Spanish red-flag phrases, weight gain over the plan's daily or weekly limit) and then through Claude's
   triage. Either one can raise an alert on the nurse dashboard. A rule-level emergency gets a fixed
   "call 911 now" text before the model is called. The agent never changes a medication or gives a diagnosis.
4. **Tracks weight from texts.** Numbers like "154 this morning" are parsed, compared with the last one, and
   charted on the dashboard against the daily limit.

**Who it is for:** heart-failure and other high-readmission discharges, run by the hospital's transitional-care
nurses. A first pilot would be one heart-failure clinic, 20-30 patients for 30 days, with nurses reviewing every
plan and every alert, measuring alert precision, teach-back scores and 30-day readmissions against usual care.

## How it works

```
patient's iPhone ──iMessage──▶ Photon 2.0 shared line
                                   │  list_messages (poll every 2 s)
                                   ▼
                       homeward/channel.py ──▶ server.handle_incoming
                                                 ├─ safety.check   (fixed rules, no model)
                                                 ├─ brain.respond  (Claude, structured output:
                                                 │                  reply, escalate, teach-back result)
                                                 ├─ store          (SQLite)
                                                 └─ channel.send ──▶ Photon send_message ──▶ patient
nurse dashboard (/) ◀── /api/state (polled) ── alerts, conversation, plan, teach-back
```

| File | What it does |
| - | - |
| `homeward/brain.py` | The two Claude calls (`claude-opus-5-5`, structured outputs via `messages.parse` + Pydantic). `make_plan` reads the letter; `respond` answers one text and returns a triage decision. |
| `homeward/safety.py` | Red-flag rules that run before the model and do not depend on it. |
| `homeward/channel.py` | `PhotonChannel` (official Photon 2.0 Python client) and `StubChannel` (local phone page) with the same interface. |
| `homeward/server.py` | FastAPI app: message loop, dashboard API, check-in endpoint. |
| `homeward/store.py` | SQLite tables for patients, messages, alerts and teach-back answers. |
| `homeward/static/` | Nurse dashboard and the stub phone page. |

Design choices we can defend:

- **Rules before the model.** The phrase rules are plain regular expressions (with negation handling, so
  "no chest pain today" does not fire) and do not call the model. The weight rules use the limits from the
  nurse-approved plan, falling back to 3 lb/day and 5 lb/week if the letter gives none. A rule-level
  emergency sends a fixed 911 text immediately. If the model call fails or times out (20 s, one retry),
  the patient gets a holding reply and the nurse gets an alert.
- **Nurse approval.** Claude's plan is a draft until a nurse clicks Approve, so nothing extracted by the model
  reaches the patient unchecked.
- **Structured outputs, not prose parsing.** The reply, escalation level and teach-back verdict come back as
  validated fields.
- **The model only uses the plan.** Every turn sends the extracted plan as context; the system prompt
  forbids changing medications or diagnosing.
- **Polling instead of webhooks.** Photon's iMessage guide uses `list_messages` polling; it needs no public
  URL, which matters on hackathon Wi-Fi. Photon's Socket.IO events are the next step for production.
- **Shared line limits.** A Photon shared iMessage line cannot start a conversation, so the patient texts
  first (the discharge paperwork would say "text HELLO to ..."). After that, the dashboard's
  "Send day N check-in" button sends the morning check-in.

## Real vs simulated

| Part | Status |
| - | - |
| Claude plan extraction and replies | Real API calls to `claude-opus-5-5`. |
| Photon 2.0 iMessage | Real. Tested live on 15 Nov 2026 on a Photon 2.0 shared iMessage line: texts from an iPhone were received through `list_messages`, and replies were sent with `send_message` about 4 s later, including the weight-gain alert. |
| Stub phone (`/phone`) | Simulated phone used when no Photon key is set. Messages go through the same agent code. |
| Patient and discharge letter | Fictional (`samples/heart_failure.txt`). No real patient data. |
| Nurse callback | The alert appears on the dashboard; nobody is actually paged. |
| "Day N" | Advanced by a button so a week fits in a demo. |

Known limits: the red-flag rules cover English and Spanish only and will miss phrasings they were not written
for (the model check runs on every message as a second layer); the model judges teach-back answers; the
dashboard has no login; there is no HIPAA/BAA arrangement with any vendor in the path; Photon 2.0 beta iMessage
supports text and images only, so there are no tapbacks.

This is a hackathon prototype, not a medical device. It has not been clinically validated.

## Run it

Python 3.11+.

```bash
pip install -r requirements.txt
cp .env.example .env.local   # add ANTHROPIC_API_KEY; Photon values optional
python -m uvicorn homeward.server:app --port 8030
```

Open http://localhost:8030 (nurse dashboard). Without Photon credentials, open http://localhost:8030/phone
to play the patient.

With Photon 2.0 (https://app.beta.photon.codes):

1. Create a project and an API key with `project:read` and `project:write`.
2. Under iMessage, add the phone number you will text from and assign a line from the shared pool.
3. Set `PHOTON_API_KEY`, `PHOTON_PROJECT_ID` and `PHOTON_AGENT_HANDLE` (the assigned number), restart.
4. Enroll a patient with your own number, then text the assigned number from your iPhone.

Tests: `python -m pytest -q`.

## Credits

- [Photon 2.0](https://photon.codes) beta and its Python client `photonhq-api` 0.5.0: iMessage delivery.
- [Anthropic Claude API](https://platform.claude.com) and the `anthropic` Python SDK: model `claude-opus-5-5`.
- [FastAPI](https://fastapi.tiangolo.com), [Uvicorn](https://www.uvicorn.org), [Pydantic](https://docs.pydantic.dev),
  [pytest](https://pytest.org), Python's built-in `sqlite3`.
- Readmission figure: Jencks SF, Williams MV, Coleman EA. Rehospitalizations among patients in the Medicare
  fee-for-service program. N Engl J Med 2009;360:1418-28.
- Built during HackPrinceton Fall 2026 by team FER, with Claude Code (Anthropic) used as a coding assistant.
