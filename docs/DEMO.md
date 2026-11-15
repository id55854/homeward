# Homeward: 2-minute demo

**Before judges arrive:**
- Server running on Photon: `python -m uvicorn homeward.server:app --port 8030`; dashboard open at http://localhost:8030, browser wide enough for three columns.
- Fresh database: stop the server, delete `data/homeward.db`, start again. Enroll the presenter's iMessage number as "Maria Alvarez" with **Use sample letter** → **Make plan and enroll** (about 25 s). **Leave the plan as a draft**; approving it is part of the demo.
- Presenter's iPhone in hand, Messages open on +1 628 998 8199, screen mirrored or held up next to the laptop.
- Backup: a second server without Photon keys on port 8031, its patient enrolled and approved, http://localhost:8031/phone open:
  `PHOTON_API_KEY= PHOTON_PROJECT_ID= HOMEWARD_DB=data/backup.db python -m uvicorn homeward.server:app --port 8031`.
  If Photon or the Wi-Fi is slow, switch and say so. The script fits 2:00 only if replies arrive in about 4 s.
- The three texts below in Notes for copy-paste. The video (`homeward-demo.mp4`) ready to play if everything fails.

**0:00 - Maria (15 s)**
"About 1 in 5 Medicare patients is back in hospital within 30 days. Maria, 72, went home yesterday with heart failure, seven medications and this letter." (point at the letter) "One pill replaces another, and taking both is dangerous. If her weight goes up 3 pounds in a day, someone needs to know."

**0:15 - The plan (20 s)**
Point at the right column.
- "The nurse pasted the letter. Claude turned it into this draft: new, changed, stopped, when to call 911, when to call the nurse, and three questions to check Maria understood."
- "It's a draft. Nothing reaches Maria until the nurse approves it." Click **Approve plan**.

**0:35 - Maria texts (35 s)**
On the iPhone, send: `hi, the nurse said to text this number`
- Reply arrives over iMessage via Photon: "Welcome, today's steps, and the first teach-back question: which pill to stop, and why."
- Send: `i stopped the lisinopril because the new heart pill replaces it`
- "She got the what but not the why. Homeward explains it, and the nurse sees 'needs review' right here." (point at teach-back in the plan column)

**1:10 - The red flag (30 s)**
Send: `im up 4 pounds since yesterday and my ankles look bigger`
- Amber alert appears on the left. "Fixed rules caught 4 pounds against the letter's 3-pound limit, and the swelling, before the model ran. Maria is told a nurse will call; the nurse sees her exact words." Click **Handled**.
- If time: `tengo dolor de pecho` gets a fixed "call 911 now" text within seconds, before Claude answers.

**1:40 - How it's built (20 s)**
"Photon 2.0 gives us the iMessage line: we read messages with list_messages and answer with send_message in the same conversation. Claude Opus 5.5 does two jobs with structured outputs: letter to plan, and each text to a reply plus a triage decision. Rules run first, an emergency gets a fixed 911 text immediately, and if the model fails, the nurse gets the message. It never changes a dose."

## Likely questions

- *Why not let the model decide everything?* Rules are predictable and tested (30 cases in `tests/test_safety.py`); the model catches what rules can't, like "I feel off and my rings are tight". Both feed the same alert list.
- *What do the rules miss?* Phrasings they weren't written for, and languages other than English and Spanish. The model check runs on every message as a second layer.
- *Hallucinated doses?* The plan prompt copies doses from the letter and leaves fields empty instead of guessing, and the nurse approves the plan before the agent uses it. Replies only use that plan.
- *What if the patient doesn't text first?* Photon shared lines can't start a conversation. A dedicated or SMS number would; the check-in button works after the first text.
- *Who pays?* Hospitals carry readmission penalties for heart failure under Medicare's Hospital Readmissions Reduction Program; transitional-care nurses are the users.
- *Privacy?* Fictional patient. Real use needs a BAA with every vendor in the path, a dashboard login, and nurse review.

## Video (about 82 s)

Same format as the Furnish video: 1920×1080, seven scenes, numbered step pill bottom-left, white callout tags, dark-navy title and closing cards, one voiceover clip per scene (Kokoro TTS). Footage is stills from a recorded run of the real dashboard on the local test line (stub phone, real Claude calls); the iPhone bubbles show the exact texts from that run. The closing card says so. The live Photon iMessage path was tested separately from an iPhone. Source: `hackprinceton/video-homeward/` (`capture/record.mjs`, `film/build.mjs`, `film/vo.py`).

| # | Scene | On screen | Voiceover |
| - | - | - | - |
| 1 | Meet Maria | Title card: "Maria went home with heart failure." Chips: 7 medicines, 1 stopped, call at +3 lb | "Maria is seventy-two. She went home from hospital yesterday with heart failure, seven medicines, and a letter written for doctors. About one in five patients like her is back in hospital within thirty days." |
| 2 | ① Letter to plan | Dashboard: sample letter, draft plan appears, Approve | "Her nurse pastes the discharge letter into Homeward. Claude turns it into a plain-language plan: what's new, what changed, what to stop, and when to call. Nothing reaches Maria until the nurse approves it." |
| 3 | ② Text her where she is | iPhone bubbles over the dashboard: "hi" → welcome and first question | "Maria texts the Homeward number from her iPhone. Through Photon, the reply arrives over iMessage in seconds: today's steps, and a first question to check she understood." |
| 4 | ③ Check she understood | Teach-back answer, explanation, "needs review" on the dashboard | "She stopped the old blood pressure pill, but doesn't know why. Homeward explains that taking both is unsafe, and the nurse sees that this answer needs review." |
| 5 | ④ Red flag to a nurse | "up 4 pounds…", amber alert, weight chart | "Next morning: up four pounds, and her ankles look bigger. Fixed rules catch it against the letter's three-pound limit before the model runs. Her nurse gets an alert with her exact words." |
| 6 | ⑤ Emergencies don't wait | "tengo dolor de pecho" → "Please call 911 now" | "Chest pain, even in Spanish, gets a call nine one one text within seconds. It never waits for the model." |
| 7 | Close | Homeward logo, "Help at home. A nurse when it matters." Footer: Photon 2.0 · iMessage · Claude | "Homeward. Help at home, and a nurse when it matters. Built on Photon and Claude." |
