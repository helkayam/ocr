from __future__ import annotations

import os
import time
from typing import List, Optional

import openai
from dotenv import load_dotenv
from loguru import logger
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.models import CitedSource, RAGResponse, SearchResult
from app.retrieval import search as retrieval_search

load_dotenv()

_GROQ_MODEL = "llama-3.3-70b-versatile"
_OPENAI_MODEL = "gpt-4o-mini"
_GROQ_BASE_URL = "https://api.groq.com/openai/v1"
_MAX_RETRY_ATTEMPTS = 5

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """
You are a professional assistant for analyzing Hebrew legal documents.

Before writing your response, perform the following analysis internally—without any output:
A. Identify specific constraints in the query (sections, dates, names, factual questions).
B. Evaluate each passage: Does it contain an explicit answer (even if embedded in a discussion of exceptions), is it related without a direct answer, or is it irrelevant?
C. Determine which passages to rely on and why.
D. Ensure every claim is grounded solely in the provided passages and not on external knowledge.

Write your final response in the following format ONLY:

[One to two sentences — a concise and definitive answer to the question]

[A fluent explanation paragraph in professional Hebrew, including relevant quotes and inline page citations in the format (עמוד X)]

מספרי העמודים עליהם הסתמכתי: [comma-separated numbers]

Mandatory Output Rules:
- Write ONLY in Hebrew; no English terms, step headers, technical labels, or JSON structures.
- If no relevant information is found, return ONLY the following phrase: "המידע המבוקש לא נמצא במסמכים שסופקו."
"""



def _build_user_message(query: str, context: List[SearchResult]) -> str:
    if not context:
        context_block = "(אין הקשר זמין)"
    else:
        passages = []
        for i, r in enumerate(context, start=1):
            passages.append(
                f"[קטע {i} | מסמך: {r.document_id}, עמוד {r.page_num}]\n{r.text}"
            )
        context_block = "\n\n---\n\n".join(passages)

    return (
        f"שאלה: {query}\n\n"
        f"קטעי הקשר ({len(context)} קטעים):\n\n"
        f"{context_block}\n\n"
        "הוראה: בצע את ניתוח הקטעים פנימית, לאחר מכן כתוב תשובה עברית בפורמט הנדרש (תשובה ישירה + הרחבה)."
    )


# ---------------------------------------------------------------------------
# LLM client factory
# ---------------------------------------------------------------------------

def _get_client() -> tuple[openai.OpenAI, str]:
    """Return (openai_client, model_name) based on LLM_PROVIDER env var."""
    provider = os.getenv("LLM_PROVIDER", "groq").lower()

    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError("OPENAI_API_KEY is not set. Add it to your .env file.")
        return openai.OpenAI(api_key=api_key), _OPENAI_MODEL

    # Default: groq
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError("GROQ_API_KEY is not set. Add it to your .env file.")
    return openai.OpenAI(api_key=api_key, base_url=_GROQ_BASE_URL), _GROQ_MODEL


# ---------------------------------------------------------------------------
# API call with retry on rate-limit
# ---------------------------------------------------------------------------

@retry(
    retry=retry_if_exception_type(openai.RateLimitError),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    stop=stop_after_attempt(_MAX_RETRY_ATTEMPTS),
    reraise=True,
)
def _call_llm(client: openai.OpenAI, model: str, messages: list) -> str:
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.1,
    )
    return response.choices[0].message.content


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate(query: str, context: List[SearchResult]) -> RAGResponse:
    """Generate a grounded Hebrew answer from *context* for *query*."""
    client, model = _get_client()
    provider = os.getenv("LLM_PROVIDER", "groq").lower()

    user_message = _build_user_message(query, context)
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    logger.info(
        "RAG generate: provider={} model={} query={!r} context_chunks={}",
        provider, model, query, len(context),
    )
    logger.debug("\n====== SYSTEM PROMPT ======\n{}\n===========================", _SYSTEM_PROMPT)
    logger.debug(
        "\n====== USER MESSAGE ======\n{}\n==========================", user_message
    )

    _t1 = time.perf_counter()
    answer = _call_llm(client, model, messages)
    logger.info(
        "Latency - Generation (Stage 3): {:.2f}s ({} chars)",
        time.perf_counter() - _t1,
        len(answer),
    )

    sources = [
        CitedSource(document_id=r.document_id, page_num=r.page_num)
        for r in context
    ]
    return RAGResponse(query=query, answer=answer, sources=sources)


def answer(
    query: str,
    top_k: int = 5,
    workspace_id: Optional[str] = None,
) -> RAGResponse:
    """End-to-end RAG: retrieve context then generate an answer.

    Primary entry point for the CLI and API layers.
    """
    context = retrieval_search.search(query, top_k=top_k, workspace_id=workspace_id)
    return generate(query, context)
