"""
Extract structured emergency action intent from a Hebrew RAG answer
using LLM function-calling (Groq / OpenAI, mirroring generator.py pattern).
"""
from __future__ import annotations

import json
import os
from typing import Literal

import openai
from dotenv import load_dotenv
from loguru import logger
from pydantic import BaseModel

load_dotenv()

_GROQ_BASE_URL = "https://api.groq.com/openai/v1"
_GROQ_MODEL = "llama-3.3-70b-versatile"
_OPENAI_MODEL = "gpt-4o-mini"

_INTENT_TOOL = {
    "type": "function",
    "function": {
        "name": "extract_emergency_intent",
        "description": (
            "Extract the emergency action intent from a Hebrew emergency-protocol answer. "
            "Identify what physical action should be taken, the type of geo-facility to "
            "navigate to, and the urgency level."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": (
                        "The primary emergency action in English. "
                        "Examples: 'proceed_to_shelter', 'shelter_in_place', 'lock_down', "
                        "'evacuate', 'call_supervisor'."
                    ),
                },
                "target_type": {
                    "type": "string",
                    "enum": ["shelter", "exit", "muster_point", "extinguisher", "assembly", "none"],
                    "description": (
                        "The type of geo-feature the occupant should proceed to. "
                        "'shelter' = protected room or safe room. "
                        "'exit' = evacuation exit or emergency door. "
                        "'muster_point' = designated rally point outside the building. "
                        "'extinguisher' = fire extinguisher location (HAZMAT/fire only). "
                        "'assembly' = assembly area for mass evacuation. "
                        "'none' = purely non-spatial action (call someone, stay in place, report to supervisor)."
                    ),
                },
                "urgency": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "critical"],
                    "description": (
                        "The urgency level inferred from the Hebrew answer. "
                        "If there is any contradiction, ambiguity, or missing context "
                        "regarding the severity of the situation, you must strictly "
                        "default to urgency: critical."
                    ),
                },
            },
            "required": ["action", "target_type", "urgency"],
        },
    },
}

_SYSTEM_PROMPT = (
    "You are an emergency protocol analyst. "
    "Given a Hebrew emergency-protocol answer, extract the required emergency action, "
    "the type of physical location to navigate to (if any), and the urgency level. "
    "CRITICAL RULE: If there is any contradiction, ambiguity, or missing context "
    "regarding the severity of the situation, you must strictly default to urgency: critical."
)

_SAFE_FALLBACK = {"action": "proceed_to_shelter", "target_type": "shelter", "urgency": "critical"}


class IntentResult(BaseModel):
    action: str
    target_type: Literal["shelter", "exit", "muster_point", "extinguisher", "assembly", "none"]
    urgency: Literal["low", "medium", "high", "critical"]


def _get_client() -> tuple[openai.OpenAI, str]:
    provider = os.getenv("LLM_PROVIDER", "groq").lower()
    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError("OPENAI_API_KEY is not set.")
        return openai.OpenAI(api_key=api_key), _OPENAI_MODEL
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError("GROQ_API_KEY is not set.")
    return openai.OpenAI(api_key=api_key, base_url=_GROQ_BASE_URL), _GROQ_MODEL


def extract_intent(rag_answer: str) -> IntentResult:
    """
    Parse a Hebrew RAG answer via LLM function-calling to extract
    {action, target_type, urgency}.  Falls back to safe defaults on any error.
    """
    try:
        client, model = _get_client()
        response = client.chat.completions.create(
            model=model,
            temperature=0.0,
            tools=[_INTENT_TOOL],
            tool_choice={"type": "function", "name": "extract_emergency_intent"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": rag_answer},
            ],
        )
        tool_calls = response.choices[0].message.tool_calls
        if not tool_calls:
            raise ValueError("LLM returned no tool call")
        args = json.loads(tool_calls[0].function.arguments)
        result = IntentResult(**args)
        logger.debug("intent_extractor: {}", result)
        return result
    except Exception as exc:
        logger.error("intent_extractor: failed ({}) — using safe fallback", exc)
        return IntentResult(**_SAFE_FALLBACK)
