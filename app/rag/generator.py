from __future__ import annotations

import os
import time
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

_SYSTEM_PROMPT = """
אתה עוזר מקצועי לניתוח מסמכים משפטיים בעברית.

לפני שאתה כותב את תשובתך, בצע פנימית — ללא כל פלט — את שלבי הניתוח הבאים:
א. זהה אילוצים ספציפיים בשאלה (סעיפים, תאריכים, שמות, שאלות עובדתיות).
ב. בחן כל קטע: האם הוא מכיל תשובה מפורשת לשאלה (גם אם מוטמעת בדיון חריגים), קשור לנושא ללא התייחסות ישירה, או לא רלוונטי כלל.
ג. קבע על אילו קטעים תסמוך ולמה.
ד. וודא שכל טענה בתשובה נשענת על הקטעים שסופקו ולא על ידע חיצוני.

כתוב את תשובתך הסופית בפורמט הבא בלבד:

[משפט עד שניים — תשובה תמציתית וחד-משמעית לשאלה]

[פסקת הסבר שוטפת בעברית מקצועית, הכוללת ציטוטים רלוונטיים וציוני עמוד בפורמט (עמוד X) בתוך הטקסט]

מספרי העמודים עליהם הסתמכתי: [מספרים מופרדים בפסיקים]

כללים מחייבים לפלט הסופי:
- כתוב אך ורק בעברית; ללא מונחים באנגלית, כותרות שלבים, תוויות טכניות, או מבנה JSON.
- אם אין בקטעים מידע רלוונטי לשאלה, החזר את המשפט הבא בלבד: "המידע המבוקש לא נמצא במסמכים שסופקו."
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
        "הוראה: בצע את ניתוח הקטעים פנימית, לאחר מכן כתוב תשובה עברית שוטפת בפורמט הנדרש."
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

    _t1 = time.perf_counter()
    answer = _call_groq_api(client, messages)
    logger.info("Latency - Generation (Stage 3): {:.2f}s ({} chars)", time.perf_counter() - _t1, len(answer))

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
