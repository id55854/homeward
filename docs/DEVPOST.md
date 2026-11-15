# Homeward: Devpost text

**Tagline:** An iMessage companion for the first weeks after a hospital stay. It turns the discharge letter into a plan, checks the patient understood it, and gets a nurse when something is wrong.

**Tracks:** Healthcare (main track); [Photon] Build a Messaging Agent using Photon 2.0

**Video:** `homeward-demo.mp4` (82 s, link on the Devpost page)

## Inspiration

About 1 in 5 Medicare patients who leave hospital is back within 30 days (Jencks et al., NEJM 2009: 19.6%). Heart failure is one of the most common reasons. The patient goes home with a letter written for clinicians: "Furosemide 40 mg PO daily (NEW DOSE)", "STOP lisinopril", "call if weight increases by 3 lb in one day". If they misread one line, or gain three pounds of fluid and tell nobody, they are back in the emergency room.

Nurses already use **teach-back**: ask the patient to explain the plan in their own words. There is no time to do it every day after discharge. Patients already text, so we put the follow-up in iMessage.

## What it does

Maria is 72 and went home with heart failure, seven medications and a two-page letter.

1. **Letter to plan.** The nurse pastes the discharge letter into the dashboard. Claude turns it into a draft plan: each medication marked new, changed, stopped or unchanged, daily checks, "call 911 if", "call the nurse if", weight limits, follow-up dates, and three teach-back questions about the most dangerous misunderstandings. Everything is written for a 5th-grade reader, in the patient's language.
2. **Nurse approves.** The plan is a draft until the nurse clicks Approve. Before that, the patient only gets a holding message.
3. **Texts the patient where she already is.** Maria texts the Homeward number from her iPhone. Over iMessage, through Photon 2.0, she gets a welcome, today's steps and the first teach-back question.
4. **Checks understanding.** "I stopped the lisinopril because the new pill replaces it" gets the what but not the why (taking both is unsafe). Homeward explains the missing part, and the nurse sees "needs review" next to that question.
5. **Escalates red flags to a person.** Every message goes through fixed rules first, then Claude's triage. "Up 4 pounds since yesterday and my ankles look bigger" raises an alert on the nurse dashboard with her exact words and the reason (4 lb against the letter's 3 lb limit, plus swelling). Maria is told a nurse will call.
6. **Emergencies don't wait for the model.** "Tengo dolor de pecho" (chest pain, in Spanish) gets a fixed "call 911 now" text within seconds, before Claude is even called.
7. **Daily check-ins and a weight trend.** The nurse can send each morning's check-in. Weights Maria texts ("154 this morning") are charted, and a jump over the limit since her last number raises an alert.

Homeward never changes a medication, never diagnoses, and hands anything uncertain to the nurse.

## How we built it

- **Photon 2.0** (beta) with a shared iMessage line and the official Python client `photonhq-api`: `list_messages` to receive, `send_message` to reply in the same conversation, `set_space_typing` for the typing indicator. Polling instead of webhooks because it needs no public URL on hackathon Wi-Fi.
- **Claude** (`claude-opus-5-5`) through the Anthropic Python SDK with structured outputs (`messages.parse` + Pydantic). Two calls: letter to plan, and one patient text to a reply plus `escalate: none | nurse | emergency` plus the teach-back verdict. The code acts on fields, not on prose.
- **Fixed safety rules** in plain Python run before the model: English and Spanish red-flag phrases with negation handling ("no chest pain today" does not fire), shortness of breath at rest, confusion, swelling, weight gain in a day or a week, and comparison with the last weight the patient texted. 30 unit tests. The phrase rules never call the model; the weight rules use the limits in the nurse-approved plan, with 3 lb/day and 5 lb/week defaults.
- **Fail toward a human.** Patient-facing model calls time out after 20 s; any failure sends a holding reply and puts the message on the nurse dashboard.
- **FastAPI + SQLite** backend and a single-page nurse dashboard in plain HTML/JS. A local stub phone with the same interface as the Photon channel let us build before our Photon key arrived and is our demo backup.

## Challenges

- Photon shared iMessage lines cannot start a conversation, so the patient has to text first; the daily check-in only works after that.
- A reviewer broke our first rule set in minutes: "no chest pain today" triggered an emergency, and "150 yesterday, 154 today" was missed. We added clause-level negation, absolute weight deltas, weekly limits and Spanish, with a test for each case.
- Keeping the agent useful without giving medical advice: it answers only from the approved plan, never changes a dose, and escalates when unsure.
- Text-message style in two languages: short, plain words, no markdown.

## Accomplishments

- A real round trip on a real phone: iMessage in, Claude reply out through Photon in about 4 seconds.
- Two independent safety paths (rules and model) feeding one nurse alert list, and a nurse sign-off before any model output reaches the patient.

## What we learned

- Structured outputs make an LLM agent easy to wire into real decisions: `escalate: "nurse"` is a field, not a sentence to parse.
- Teach-back fits messaging well: one question, one answer, one verdict the nurse can see.
- Rules need adversarial tests as much as prompts do.

## What's next

- A pilot with one heart-failure clinic: 20-30 patients for 30 days, nurses reviewing every plan and alert, measuring alert precision, teach-back scores and 30-day readmissions against usual care.
- Photon Socket.IO events with replay cursors instead of polling; a dedicated number so Homeward can send the first message.
- A voice check-in for patients who don't text.
- Dashboard login, BAAs with every vendor in the path, more languages in the fixed rules.

## Real vs simulated

The iMessage conversation is real: tested from an iPhone on a Photon 2.0 shared line. The patient and discharge letter are fictional. Nobody is paged; alerts appear on the dashboard. "Day N" is advanced by a button. The model judges teach-back answers; the dashboard has no login; there is no HIPAA/BAA arrangement yet. Not clinically validated.

## Built with

Photon 2.0, photonhq-api, Anthropic Claude API (claude-opus-5-5), anthropic Python SDK, FastAPI, Uvicorn, Pydantic, SQLite, pytest. Demo video: HyperFrames, GSAP, Kokoro TTS, Playwright, FFmpeg. Built during HackPrinceton Fall 2026 by team FER, with Claude Code used as a coding assistant.
