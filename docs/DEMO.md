# Demo script (2 minutes)

## Before judges arrive

- Server running: `python -m uvicorn homeward.server:app --port 8030`; dashboard open at http://localhost:8030.
- Fresh database: stop the server, delete `data/homeward.db`, start again.
- Enroll the presenter's phone **before** the demo (plan extraction takes about 25 s): name "Maria Alvarez",
  the presenter's iMessage number, "Use sample letter", "Make plan and enroll".
- Presenter's iPhone in hand, Messages open on the Homeward number, screen mirrored or held up.
- Backup: if Photon or the Wi-Fi fails, open http://localhost:8030/phone and use the same lines there.
- Have the three texts below in Notes for copy-paste.

## Script

**0:00 - the problem (15 s)**
"About 1 in 5 Medicare patients is back in hospital within 30 days. Maria, 72, went home yesterday with heart
failure, seven medications, and this letter." (point at the letter) "One of those pills replaces another, and
taking both is dangerous. If her weight goes up 3 pounds in a day, someone needs to know."

**0:15 - the plan (20 s)**
Show the right column. "The nurse pasted the letter. Claude turned it into this: what's new, what's changed,
what to stop, when to call 911, when to call the nurse, and three questions to check Maria understood."

**0:35 - Maria texts (35 s)**
On the iPhone, send: `hi, the nurse said to text this number`
Reply arrives over iMessage via Photon: welcome, today's steps, first teach-back question about the stopped pill.
Send: `i stop the lisinopril because the new heart pill replaces it`
"She got the what but not the why. Homeward explains it, and the nurse sees 'needs review' right here."
(point at teach-back in the plan column)

**1:10 - the red flag (30 s)**
Send: `im up 4 pounds since yesterday and my ankles look bigger`
Alert appears on the left in amber. "A fixed rule caught the 4 pounds against the letter's 3-pound limit, before
the model even ran. Claude flagged the ankle swelling too. Maria is told a nurse will call; the nurse sees her
exact words." Click "Handled".

**1:40 - how it's built (20 s)**
"Photon 2.0 gives us the iMessage line: we poll list_messages and reply with send_message in the same
conversation. Claude Opus 5.5 does two things with structured outputs: letter to plan, and message to reply plus
triage. Safety rules run first, and if the model fails, the nurse gets the message. It never changes a dose."

## Likely questions

- **Why not let the model decide everything?** Rules are predictable and testable (`tests/test_safety.py`);
  the model catches what rules can't, like "my ankles look bigger". Both feed the same alert list.
- **What if the patient doesn't start the chat?** Photon shared lines need the patient to text first. A dedicated
  line or SMS number would allow the first message; the check-in button works after the first text.
- **Hallucinated doses?** The plan prompt copies doses from the letter and leaves fields empty instead of guessing;
  the nurse sees the plan before the patient does. Replies only use that plan.
- **Privacy?** Demo uses a fictional patient. Real use needs a BAA with every vendor in the path and nurse review.
