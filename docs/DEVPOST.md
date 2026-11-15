# Homeward (Devpost text)

**Track:** [Photon] Build a Messaging Agent using Photon 2.0

## Tagline

A discharge companion that texts patients their plan, checks they understood it, and gets a nurse when something is wrong.

## Inspiration

About 1 in 5 Medicare patients who leave hospital is readmitted within 30 days. Discharge letters are written
for clinicians: "Furosemide 40 mg PO daily (NEW DOSE)", "call if weight increases by 3 lb in one day". A patient
who misreads one line can end up back in the emergency room. Nurses already use "teach-back" (ask the patient to
explain the plan in their own words), but there is no time to do it every day after the patient goes home.
Patients already text. So we put the follow-up where they already are: iMessage.

## What it does

- A nurse pastes the discharge letter into the dashboard and enters the patient's phone number and language.
- Claude turns the letter into a plan: medications marked new, changed or stopped, daily checks, "call 911 if",
  "call the nurse if", follow-up dates, and three teach-back questions.
- The patient texts the Homeward number. The agent welcomes them, gives today's steps, and asks the teach-back
  questions one at a time. It records whether each answer covered the key points.
- Every patient message is checked by fixed rules (emergency phrases, weight gain over the letter's threshold)
  and by Claude's triage. A red flag puts an alert on the nurse dashboard with the patient's exact words and the
  reason, and the patient is told a nurse will call (or to call 911).
- Each morning the dashboard can send a check-in asking for the day's weight and symptoms.

## How we built it

- **Photon 2.0** (beta, shared iMessage line) with the official Python client `photonhq-api`: `list_messages`
  to receive, `send_message` to reply in the same space, `set_space_typing` for the typing indicator.
- **Claude** (`claude-opus-5-5`) through the Anthropic Python SDK with structured outputs (`messages.parse` and
  Pydantic models). One call extracts the plan from the letter; one call per message returns the reply, the
  escalation level and the teach-back verdict as validated fields.
- **Fixed safety rules** in plain Python run before the model, so an emergency phrase or a 4 lb weight gain
  raises an alert even if the model call fails. A failed model call sends a holding reply and alerts the nurse.
- **FastAPI + SQLite** backend, and a single-page nurse dashboard in plain HTML/JS.
- A local stub phone with the same interface as the Photon channel, so we could build before our Photon key arrived.

## Challenges

- Photon shared iMessage lines cannot start a conversation, so the patient has to text first; scheduled
  check-ins only work after that first message.
- Keeping the agent from giving medical advice while still being useful: it answers only from the extracted plan,
  never changes a dose, and hands anything uncertain to the nurse.
- Text-message style: short, plain words, no markdown, in the patient's language.

## Accomplishments

- A full loop from discharge letter to plan to a real text conversation to a nurse alert, in one evening.
- Two independent safety paths (rules and model) that both feed the same nurse alert list.

## What we learned

- Structured outputs make an LLM agent much easier to wire into real decisions: the code acts on a field
  (`escalate: "nurse"`), not on a sentence.
- Teach-back is a good fit for messaging: one question, one answer, one verdict.

## What's next

- Photon Socket.IO events with replay cursors instead of polling.
- A voice check-in on a dedicated Photon number for patients who do not text.
- Scheduled daily check-ins and a weight trend chart from the numbers patients send.
- Review by nurses and a pilot with a heart failure clinic before any real use.

## Built with

Photon 2.0, photonhq-api, Anthropic Claude API (claude-opus-5-5), anthropic Python SDK, FastAPI, Uvicorn,
Pydantic, SQLite, pytest. Built with Claude Code as a coding assistant.

## Real vs simulated

The patient and discharge letter are fictional. Nobody is paged; alerts appear on the dashboard.
"Day N" is advanced by a button. Not clinically validated.
