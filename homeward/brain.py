"""Claude calls. Two jobs:

1. make_plan: discharge letter -> structured plan (meds, daily checks, red flags,
   teach-back questions) the rest of the system works from.
2. respond: one patient text -> one reply text plus a triage decision.

Both use structured outputs so the code gets validated fields, not prose to parse.
"""
import json
from typing import Literal, Optional

import anthropic
from pydantic import BaseModel, Field

from . import config

client = anthropic.Anthropic()


class Medication(BaseModel):
    name: str
    dose: str
    when: str = Field(description="When to take it, in plain words, e.g. 'every morning with breakfast'")
    purpose: str = Field(description="What it is for, in plain words")
    change: Literal["new", "changed", "stopped", "same"]


class TeachBack(BaseModel):
    question: str = Field(description="A question the patient answers in their own words")
    key_points: list[str] = Field(description="What a correct answer must include")


class Plan(BaseModel):
    diagnosis_plain: str = Field(description="Why they were in hospital, 1-2 short sentences, plain words")
    medications: list[Medication]
    daily_checks: list[str] = Field(description="Things to do every day, e.g. 'Weigh yourself each morning after the toilet'")
    call_911_if: list[str]
    call_nurse_if: list[str]
    weight_gain_alert_lb: Optional[float] = Field(description="Pounds of gain in a day that the letter says to report, or null")
    follow_up: list[str] = Field(description="Appointments and tests with dates")
    teach_back: list[TeachBack] = Field(description="3 questions covering the most dangerous misunderstandings")
    welcome_message: str = Field(description="First text to the patient: who we are, what we will do, under 320 characters")


class Turn(BaseModel):
    reply: str = Field(description="Text message to send to the patient")
    escalate: Literal["none", "nurse", "emergency"]
    escalation_reason: str = Field(description="One line for the nurse; empty if escalate is none")
    teach_back_question: Optional[str] = Field(description="If this message answered a teach-back question, that question; else null")
    teach_back_correct: Optional[bool] = Field(description="Whether that answer covered the key points; null if not a teach-back answer")


PLAN_SYSTEM = """You turn hospital discharge letters into a plan a patient can follow at home.
Copy medication names, doses and dates exactly from the letter. Never invent a medication,
dose, threshold or appointment that is not in the letter; leave a field empty instead.
Write for a reader at a 5th-grade level in the requested language. The welcome message
is a text message: warm, short, no markdown."""

TURN_SYSTEM = """You are Homeward, a text-message companion for a patient who just went home
from hospital. You work for their care team, and a nurse reads every alert you raise.

Your job, in order of importance:
1. Safety. If the patient reports anything on the "call 911" list, tell them to call 911 now
   and set escalate=emergency. If they report anything on the "call the nurse" list, or
   anything new that worries you, or you are not sure, set escalate=nurse and tell them a
   nurse will call them soon.
2. Understanding. Ask the teach-back questions one at a time, at natural moments, and
   check the answer against the key points. If an answer is wrong or incomplete, explain
   the right answer kindly in one or two sentences, then move on.
3. Daily plan. Answer questions about their meds, checks and appointments using only the plan.

Rules:
- Never start, stop or change a medication or dose. Never diagnose. If asked, say the
  nurse or doctor decides that and set escalate=nurse.
- Text-message style: plain words, short sentences, at most 3 short paragraphs, no markdown,
  no bullet symbols. Write in the patient's language.
- Use only facts from the plan below or what the patient told you."""


def _call(model_cls, system: str, messages: list[dict], effort: str):
    """One structured call. Refusals become an exception the caller handles."""
    response = client.messages.parse(
        model=config.MODEL,
        max_tokens=8000,
        system=system,
        messages=messages,
        output_format=model_cls,
        output_config={"effort": effort},
    )
    if response.stop_reason == "refusal" or response.parsed_output is None:
        raise RuntimeError(f"model returned no usable output (stop_reason={response.stop_reason})")
    return response.parsed_output


def make_plan(letter: str, language: str) -> dict:
    plan = _call(
        Plan,
        PLAN_SYSTEM,
        [{"role": "user", "content": f"Language for the patient: {language}\n\nDischarge letter:\n{letter}"}],
        effort="medium",
    )
    return plan.model_dump()


def _context(patient: dict, teachback_done: list[dict]) -> str:
    done = "\n".join(f"- {t['question']} -> {'correct' if t['correct'] else 'needs review'}" for t in teachback_done)
    return (
        f"Patient: {patient['name']}. Language: {patient['language']}. Day {patient['day']} at home.\n\n"
        f"Plan (JSON):\n{json.dumps(patient['plan'], indent=1)}\n\n"
        f"Teach-back answered so far:\n{done or '- none yet'}"
    )


def respond(patient: dict, history: list[dict], teachback_done: list[dict], instruction: str | None = None) -> Turn:
    """history: messages rows (direction in/out), oldest first, already including the new inbound text."""
    messages: list[dict] = [
        {"role": "user", "content": f"[Care-team context, not from the patient]\n{_context(patient, teachback_done)}"},
        {"role": "assistant", "content": "Understood. I will reply to the patient's texts."},
    ]
    for m in history:
        role = "user" if m["direction"] == "in" else "assistant"
        if messages[-1]["role"] == role:  # keep strict alternation
            messages[-1]["content"] += "\n" + m["text"]
        else:
            messages.append({"role": role, "content": m["text"]})
    if instruction:
        # Proactive check-in: the care team, not the patient, asks for a message.
        note = f"[Care-team instruction, not from the patient] {instruction}"
        if messages[-1]["role"] == "user":
            messages[-1]["content"] += "\n\n" + note
        else:
            messages.append({"role": "user", "content": note})
    return _call(Turn, TURN_SYSTEM, messages, effort="low")
