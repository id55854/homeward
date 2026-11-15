"""Fixed red-flag rules that run before the model.

The model also judges every reply, but these rules do not depend on it:
if a patient types one of these, the nurse is alerted even if the model
call fails or misreads the message.
"""
import re

# Phrases that mean "call 911 now" for almost any discharge.
EMERGENCY_PATTERNS = [
    r"chest (pain|pressure|tightness)",
    r"can'?t breathe|cannot breathe|can not breathe|struggling to breathe|gasping",
    r"pass(ed)? out|fainted|unconscious",
    r"(face|mouth) (is )?droop",
    r"slurred speech|can'?t speak",
    r"cough(ing)? (up )?blood|vomit(ing)? blood",
    r"(kill|hurt) myself|suicid",
]

# "up 3 pounds", "gained 4 lbs", "3.5 lb heavier", "weight went up 2 kg"
WEIGHT_GAIN = re.compile(
    r"(?:gain(?:ed)?|up|heavier|went up|increase[d]?)\D{0,20}?(\d+(?:\.\d+)?)\s*(lb|lbs|pound|pounds|kg|kilo)"
    r"|(\d+(?:\.\d+)?)\s*(lb|lbs|pound|pounds|kg|kilo)s?\s*(?:up|heavier|more|gain)",
    re.IGNORECASE,
)


def check(text: str, plan: dict) -> tuple[str, str] | None:
    """Return (level, reason) when a fixed rule fires, else None."""
    lowered = text.lower()
    for pattern in EMERGENCY_PATTERNS:
        if re.search(pattern, lowered):
            return "emergency", f"Emergency phrase in message (rule: {pattern})"

    limit = plan.get("weight_gain_alert_lb")
    match = WEIGHT_GAIN.search(text)
    if limit and match:
        amount = float(match.group(1) or match.group(3))
        unit = (match.group(2) or match.group(4)).lower()
        pounds = amount * 2.2 if unit.startswith("k") else amount
        if pounds >= float(limit):
            return "nurse", f"Weight up {pounds:.1f} lb; discharge letter says call at {limit} lb"
    return None
