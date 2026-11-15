"""Fixed red-flag rules that run before the model.

The phrase rules are plain regular expressions and do not use the model at
all. The weight rules use the limits from the plan the nurse approved (the
plan was extracted by Claude from the discharge letter); if the letter gave
no limit, they fall back to 3 lb in a day and 5 lb in a week, the common
heart-failure instruction.

Known limits: English and Spanish phrases only; a phrase rule is skipped when
a negation ("no", "not", "didn't", "sin", "nunca"...) comes within four words
before it in the same clause. The model reviews every message as well.
"""
import re

DEFAULT_DAY_LB = 3.0
DEFAULT_WEEK_LB = 5.0

BREATH = (r"short(ness)? of breath|out of breath|catch (my|her|his) breath|trouble breathing|hard to breathe|"
          r"breathless|winded|falta de aire|me falta el aire|(me )?cuesta respirar")
AT_REST = r"at rest|resting|sitting|lying|laying|still|doing nothing|even when|severe|very|en reposo|sentad[oa]|acostad[oa]|mucha"

# (level, label, pattern). Order does not matter; the most severe match wins.
PHRASES = [
    ("emergency", "chest pain", r"chest (pain|pressure|tightness|hurts)|pain in (my|the) chest|dolor (en el|de|del) pecho|presi[oó]n en el pecho"),
    ("emergency", "cannot breathe", r"can'?t breathe|cannot breathe|can not breathe|gasping|no puedo respirar|me ahogo"),
    ("emergency", "fainting", r"pass(ed)? out|fainted|faint(ing)?\b|blacked out|unconscious|me desmay|desmayo"),
    ("emergency", "confusion", r"\bconfused\b|confusion|disoriented|don'?t know where i am|confundid[oa]|desorientad[oa]"),
    ("emergency", "stroke signs", r"(face|mouth) (is )?droop|slurred speech|can'?t speak|cara ca[ií]da"),
    ("emergency", "bleeding", r"cough(ing)? (up )?blood|vomit(ing)? blood|sangre al toser|vomit[oé] sangre"),
    ("emergency", "self-harm", r"(kill|hurt) myself|suicid|matarme"),
    ("nurse", "short of breath", BREATH),
    ("nurse", "needs more pillows", r"more pillows|sleep(ing)? sitting up|m[aá]s almohadas"),
    ("nurse", "swelling", r"swell|swollen|puffy|(ankles|legs|feet) (are |look |got )?bigger|hinchad[oa]s?|hinchaz[oó]n"),
    ("nurse", "dizziness", r"dizzy|light-? ?headed|mare(o|ad[oa])"),
    ("nurse", "low urine", r"(barely|hardly|not) (peeing|urinating)|very little (pee|urine)|casi no orino"),
]

NEGATIONS = {"no", "not", "don't", "dont", "didn't", "didnt", "never", "without", "haven't", "havent", "hasn't",
             "isn't", "wasn't", "aren't", "nor", "sin", "nunca", "ni", "tampoco", "none"}
CLAUSE_SPLIT = re.compile(r"[.;!?\n]|,|\bbut\b|\bpero\b|\bthough\b", re.IGNORECASE)

UNIT = r"(lb|lbs|pound|pounds|libras?|kg|kilos?|kilogramos?)"
RELATIVE_GAIN = re.compile(
    r"(?:gain(?:ed)?|up|heavier|went up|increase[d]?|sub[ií]|aument[eé])\D{0,20}?(\d+(?:\.\d+)?)\s*" + UNIT +
    r"|(\d+(?:\.\d+)?)\s*" + UNIT + r"\s*(?:up|heavier|more|gain|m[aá]s)",
    re.IGNORECASE,
)
WEEK = re.compile(r"week|semana|7 days|7 d[ií]as", re.IGNORECASE)
NUMBER = re.compile(r"(\d{2,3}(?:\.\d)?)\s*(lb|lbs|pounds?|libras?|kg|kilos?)?", re.IGNORECASE)


def _negated(clause: str, start: int) -> bool:
    before = re.findall(r"[a-záéíóúñ']+", clause[:start].lower())
    return any(w in NEGATIONS for w in before[-4:])


def _phrase_hits(text: str) -> list[tuple[str, str]]:
    hits = []
    for clause in CLAUSE_SPLIT.split(text):
        low = clause.lower()
        for level, label, pattern in PHRASES:
            m = re.search(pattern, low)
            if m and not _negated(low, m.start()):
                if label == "short of breath" and re.search(AT_REST, low):
                    level, label = "emergency", "short of breath at rest"
                hits.append((level, label))
    return hits


def _to_lb(value: float, unit: str | None) -> float:
    return value * 2.2046 if unit and unit.lower().startswith("k") else value


def extract_weights(text: str) -> list[float]:
    """Body weights in pounds mentioned in the text, in order (e.g. '150 yesterday, 154 today')."""
    kg_text = re.search(r"\bkg\b|kilo", text, re.IGNORECASE)
    out = []
    for m in NUMBER.finditer(text):
        value, unit = float(m.group(1)), m.group(2) or ("kg" if kg_text else None)
        lb = _to_lb(value, unit)
        if 80 <= lb <= 450:
            out.append(round(lb, 1))
    return out


def _limits(plan: dict) -> tuple[float, float, str]:
    day = plan.get("weight_gain_alert_lb")
    week = plan.get("weight_gain_week_lb")
    source = "discharge letter" if day else "default"
    return float(day or DEFAULT_DAY_LB), float(week or DEFAULT_WEEK_LB), source


def _weight_hit(text: str, plan: dict, previous_lb: float | None) -> tuple[str, str] | None:
    day_lb, week_lb, source = _limits(plan)
    weekly = bool(WEEK.search(text))
    limit = week_lb if weekly else day_lb
    period = "in a week" if weekly else "in a day"

    gain = None
    m = RELATIVE_GAIN.search(text)
    if m:
        gain = _to_lb(float(m.group(1) or m.group(3)), m.group(2) or m.group(4))
    else:
        weights = extract_weights(text)
        if len(weights) >= 2:
            gain = weights[-1] - weights[0]          # "150 yesterday, 154 today"
        elif len(weights) == 1 and previous_lb:
            gain = weights[0] - previous_lb         # today's number vs the last one she texted
            period, limit = "since the last reported weight", day_lb
    if gain is not None and gain >= limit:
        return "nurse", f"Weight up {gain:.1f} lb {period}; limit {limit:g} lb ({source})"
    return None


def check(text: str, plan: dict, previous_lb: float | None = None) -> tuple[str, str] | None:
    """Return the most severe (level, reason) found, or None."""
    hits = [(lvl, f"Patient reported {label} (fixed rule)") for lvl, label in _phrase_hits(text)]
    weight = _weight_hit(text, plan, previous_lb)
    if weight:
        hits.append(weight)
    if not hits:
        return None
    hits.sort(key=lambda h: h[0] != "emergency")
    level = hits[0][0]
    reasons = "; ".join(dict.fromkeys(r for l, r in hits))
    return level, reasons
