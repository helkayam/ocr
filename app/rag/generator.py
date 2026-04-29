from __future__ import annotations

import os
from typing import List

import groq as groq_sdk
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

GROQ_MODEL = "llama-3.3-70b-versatile"
_MAX_RETRY_ATTEMPTS = 5

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """
You are a precise document analysis assistant. You MUST follow every rule below without exception.

Rules:
1. Answer ONLY based on the context passages provided. Do not use outside knowledge.
2. Always reply in Hebrew (עברית).
3. After every factual claim, cite its source in the format: [מסמך: {document_id}, עמוד {page_num}].
4. If the answer cannot be found in the provided context, respond with this exact phrase and nothing else:
   "המידע המבוקש לא נמצא במסמכים שסופקו."
5. Never fabricate, paraphrase beyond what is stated, or infer facts not present in the context.
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
        "הוראה: יישם את פרוטוקול האימות בארבעה שלבים לפני שתנסח תשובה."
    )


# ---------------------------------------------------------------------------
# Groq API call with retry logic
# ---------------------------------------------------------------------------

@retry(
    retry=retry_if_exception_type(groq_sdk.RateLimitError),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    stop=stop_after_attempt(_MAX_RETRY_ATTEMPTS),
    reraise=True,
)
def _call_groq_api(client: groq_sdk.Groq, messages: list) -> str:
    """Single attempt to call the Groq chat completion API.

    The ``@retry`` decorator retries up to ``_MAX_RETRY_ATTEMPTS`` times with
    exponential back-off when a ``RateLimitError`` (HTTP 429) is raised.
    Any other exception propagates immediately.
    """
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        temperature=0.1,
    )
    return response.choices[0].message.content


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate(query: str, context: List[SearchResult]) -> RAGResponse:
    """Generate a grounded Hebrew answer from *context* for *query*.

    Uses the Groq LLM.  Retries automatically on HTTP 429 responses.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError("GROQ_API_KEY is not set. Add it to your .env file.")

    client = groq_sdk.Groq(api_key=api_key)
    user_message = _build_user_message(query, context)
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    logger.info("RAG generate: query={!r} context_chunks={}", query, len(context))
    logger.info("\n====== SYSTEM PROMPT ======\n{}\n===========================", _SYSTEM_PROMPT)
    logger.info("\n====== FULL USER MESSAGE (Context + Query) ======\n{}\n=================================================", user_message)

    answer = _call_groq_api(client, messages)
    logger.info("RAG answer received ({} chars)", len(answer))

    sources = [
        CitedSource(document_id=r.document_id, page_num=r.page_num)
        for r in context
    ]
    return RAGResponse(query=query, answer=answer, sources=sources)


def answer(query: str, top_k: int = 5) -> RAGResponse:
    """End-to-end RAG: retrieve context from ChromaDB, then generate an answer.

    This is the primary entry point for the CLI and API layers.
    """
    context = retrieval_search.search(query, top_k=top_k)
    return generate(query, context)
