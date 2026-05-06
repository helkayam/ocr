from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from dotenv import load_dotenv
from loguru import logger
from tabulate import tabulate
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.models import EvalResult, GoldenQuestion, RAGResponse
from app.rag import generator

load_dotenv()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# All RAG calls during evaluation are scoped to this workspace, regardless of
# what the goldset JSON files say. The goldset workspace IDs are eval fixtures
# and may not match the live index.
EVAL_WORKSPACE_ID = "0fff6cb7-8721-4399-a8fd-95d2d9b1c73e"

EVAL_DATA_DIR = Path("eval_data")
REPORT_DIR = Path("data/eval_reports")
FALLBACK_PHRASE = "המידע המבוקש לא נמצא במסמכים שסופקו."

_INTER_QUESTION_SLEEP = 1.5  # seconds between questions to avoid API rate limits
_RECALL_PAGE_TOLERANCE = 2   # ±N pages counted as a retrieval hit

_JUDGE_SYSTEM_PROMPT = """\
אתה שופט מומחה להערכת תשובות בשאלות על מסמכים משפטיים עבריים.
קיבלת תשובה צפויה ותשובה שנוצרה על ידי מערכת בינה מלאכותית.
עליך להעריך האם התשובה שנוצרה נכונה עובדתית בהשוואה לתשובה הצפויה.

החזר JSON בלבד בפורמט המדויק הבא, ללא טקסט נוסף:
{"score": 1, "reason": "..."}

כללים:
- score הוא 1 אם התשובה נכונה עובדתית, 0 אם לא.
- התמקד בנכונות עובדתית בלבד.
- התעלם מהבדלי ניסוח, סגנון, או מבנה.
- אל תכלול שום טקסט מחוץ לאובייקט ה-JSON.\
"""

# ---------------------------------------------------------------------------
# OpenAI LLM-as-a-Judge (sync, wrapped with tenacity)
# ---------------------------------------------------------------------------

@retry(
    retry=retry_if_exception_type(Exception),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(4),
    reraise=True,
)
def _call_judge(expected_answer: str, generated_answer: str) -> Tuple[float, str]:
    """Call gpt-4o-mini to judge factual accuracy. Returns (score 0.0|1.0, reason)."""
    import openai

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY is not set in .env")

    client = openai.OpenAI(api_key=api_key)
    user_msg = (
        f"תשובה צפויה:\n{expected_answer}\n\n"
        f"תשובה שנוצרה:\n{generated_answer}"
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": _JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.0,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    parsed = json.loads(raw)
    score = float(int(parsed.get("score", 0)))
    reason = str(parsed.get("reason", ""))
    return score, reason


# ---------------------------------------------------------------------------
# RAGEvaluator
# ---------------------------------------------------------------------------

class RAGEvaluator:
    """Evaluate the RAG pipeline against goldset JSON files.

    Usage:
        asyncio.run(RAGEvaluator(top_k=5).run())
        asyncio.run(RAGEvaluator().run(file_path=Path("eval_data/goldset_companies.json")))
    """

    def __init__(self, top_k: int = 5) -> None:
        self.top_k = top_k

    # ------------------------------------------------------------------
    # Metric helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_recall(question: GoldenQuestion, response: RAGResponse) -> float:
        """Recall@K with ±_RECALL_PAGE_TOLERANCE page window.

        Negative questions: correct iff zero sources are returned.
        All others: a hit when any retrieved page is within tolerance of any
        expected page, absorbing OCR index offsets.
        """
        if question.question_type == "negative":
            return 1.0 if not response.sources else 0.0
        if not question.expected_pages:
            return 1.0
        returned = [s.page_num for s in response.sources]
        for ret in returned:
            for exp in question.expected_pages:
                if abs(ret - exp) <= _RECALL_PAGE_TOLERANCE:
                    return 1.0
        return 0.0

    @staticmethod
    def _compute_accuracy(
        question: GoldenQuestion,
        response: RAGResponse,
    ) -> Tuple[float, str]:
        """LLM-as-a-Judge semantic accuracy. Returns (score 0.0|1.0, reason)."""
        if question.question_type == "negative":
            if FALLBACK_PHRASE in response.answer:
                return 1.0, "תשובה שלילית נכונה — המערכת זיהתה שהמידע לא קיים"
            return 0.0, "המערכת לא זיהתה שהמידע אינו במסמכים"

        try:
            return _call_judge(question.expected_answer, response.answer)
        except Exception as exc:
            logger.warning("Judge call failed for {}: {}", question.question_id, exc)
            return 0.0, f"שגיאה בהערכה: {exc}"

    # ------------------------------------------------------------------
    # Per-question evaluation
    # ------------------------------------------------------------------

    async def _evaluate_one(
        self, question: GoldenQuestion
    ) -> Tuple[EvalResult, Dict]:
        """Run a single question through the RAG pipeline and score it.

        Returns (EvalResult, audit_dict). The workspace is always overridden
        to EVAL_WORKSPACE_ID regardless of what the goldset specifies.
        """
        try:
            response: RAGResponse = await asyncio.to_thread(
                generator.answer,
                question.query,
                top_k=self.top_k,
                workspace_id=EVAL_WORKSPACE_ID,  # always use the live eval workspace
            )
        except Exception as exc:
            logger.warning("RAG pipeline error for {}: {}", question.question_id, exc)
            empty_result = EvalResult(
                question_id=question.question_id,
                query=question.query,
                question_type=question.question_type,
                document_id=question.document_id,
                workspace_id=EVAL_WORKSPACE_ID,
                recall=0.0,
                accuracy=0.0,
                accuracy_reason=f"RAG error: {exc}",
                generated_answer="",
                returned_pages=[],
            )
            audit = _build_audit_entry(question, empty_result)
            return empty_result, audit

        recall = self._compute_recall(question, response)
        accuracy, reason = self._compute_accuracy(question, response)
        returned_pages = [s.page_num for s in response.sources]

        result = EvalResult(
            question_id=question.question_id,
            query=question.query,
            question_type=question.question_type,
            document_id=question.document_id,
            workspace_id=EVAL_WORKSPACE_ID,
            recall=recall,
            accuracy=accuracy,
            accuracy_reason=reason,
            generated_answer=response.answer,
            returned_pages=returned_pages,
        )
        audit = _build_audit_entry(question, result)
        return result, audit

    # ------------------------------------------------------------------
    # File-level evaluation
    # ------------------------------------------------------------------

    async def _evaluate_file(
        self, path: Path, total_done: int, total_all: int, report_path: Path
    ) -> Tuple[str, List[EvalResult], float]:
        """Evaluate one goldset file.

        Appends each result to *report_path* immediately after it is scored,
        so a crash preserves everything evaluated so far.
        Returns (display_name, results, elapsed_secs).
        """
        display_name = path.stem.replace("goldset_", "").replace("_", " ").title()

        if path.stat().st_size == 0:
            print(f"\n  [SKIP] {path.name} — empty file")
            return display_name, [], 0.0

        items = json.loads(path.read_text(encoding="utf-8"))
        questions = [GoldenQuestion(**item) for item in items]
        print(f"\n  ── {path.name} ({len(questions)} questions) ──")

        t0 = time.perf_counter()
        results: List[EvalResult] = []

        for i, q in enumerate(questions):
            result, audit = await self._evaluate_one(q)
            results.append(result)

            # Persist immediately — survives any subsequent crash
            _append_result(report_path, audit)

            recall_icon = "✓" if result.recall == 1.0 else "✗"
            acc_icon = "✓" if result.accuracy == 1.0 else "✗"
            done = total_done + i + 1
            pct = done / total_all * 100
            print(
                f"  [{done:>3}/{total_all}  {pct:4.0f}%]  "
                f"{q.question_id}  {q.question_type:<10}  "
                f"recall={recall_icon}  accuracy={acc_icon}"
            )

            if i < len(questions) - 1:
                await asyncio.sleep(_INTER_QUESTION_SLEEP)

        elapsed = time.perf_counter() - t0
        return display_name, results, elapsed

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self, file_path: Optional[Path] = None) -> List[EvalResult]:
        """Run evaluation over all files in eval_data/ or a specific file.

        A JSONL report file is opened once at the start of the run and each
        question result is flushed to disk immediately after it is scored.
        If the process is killed mid-run (e.g. by a Groq 429), every result
        evaluated so far is safely preserved in the JSONL file.

        Returns the full list of EvalResult objects.
        Raises FileNotFoundError if no goldset files are found.
        """
        _silence_pipeline_logs()

        if file_path is not None:
            files = [Path(file_path)]
        else:
            files = sorted(EVAL_DATA_DIR.glob("*.json"))
            if not files:
                raise FileNotFoundError(f"No JSON files found in {EVAL_DATA_DIR}")

        total_all = _count_questions(files)

        # Create the report file once — its name never changes during this run
        report_path = _open_report(self.top_k)

        all_results: List[EvalResult] = []
        table_rows: list = []
        total_done = 0

        print(f"\n  Report    : {report_path}")
        print(f"  Workspace : {EVAL_WORKSPACE_ID}")
        print(f"  Questions : {total_all}  |  top_k={self.top_k}\n")

        for path in files:
            display_name, results, elapsed = await self._evaluate_file(
                path, total_done, total_all, report_path
            )
            total_done += len(results)
            all_results.extend(results)

            if not results:
                table_rows.append([display_name, 0, "—", "—", f"{elapsed:.0f}s"])
                continue

            avg_recall = sum(r.recall for r in results) / len(results) * 100
            avg_accuracy = sum(r.accuracy for r in results) / len(results) * 100
            table_rows.append([
                display_name,
                len(results),
                f"{avg_recall:.1f}%",
                f">>> {avg_accuracy:.1f}% <<<",
                f"{elapsed:.0f}s",
            ])

        # Append summary line — present only in reports from completed runs
        _finalize_report(report_path, all_results)
        print(f"\n  Audit report → {report_path}")

        _print_summary(table_rows, all_results)
        return all_results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _silence_pipeline_logs() -> None:
    """Replace all loguru handlers with a WARNING-only sink.

    This prevents the verbose INFO output from app.rag.generator (which logs
    the full system prompt and every user message) and app.pipeline from
    drowning out the per-question progress lines during evaluation.
    Warnings and errors still surface so real failures are visible.
    """
    logger.remove()
    logger.add(sys.stderr, level="WARNING", format="<level>{level: <8}</level> | {message}")


def _count_questions(files: List[Path]) -> int:
    """Return total number of questions across all non-empty goldset files."""
    total = 0
    for path in files:
        if path.stat().st_size > 0:
            try:
                total += len(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                pass
    return total


def _build_audit_entry(question: GoldenQuestion, result: EvalResult) -> Dict:
    return {
        "question_id": result.question_id,
        "query": result.query,
        "question_type": result.question_type,
        "document_id": result.document_id,
        "workspace_id_used": EVAL_WORKSPACE_ID,
        "expected_answer": question.expected_answer,
        "generated_answer": result.generated_answer,
        "expected_pages": question.expected_pages,
        "returned_pages": result.returned_pages,
        "recall_score": result.recall,
        "accuracy_score": result.accuracy,
        "judge_reason": result.accuracy_reason,
    }


def _open_report(top_k: int) -> Path:
    """Create a new, uniquely-named JSONL report file and write the metadata header.

    The filename is fixed for the entire run so historical reports are never
    overwritten.  Format: data/eval_reports/report_YYYYMMDD_HHMMSS.jsonl

    JSONL layout:
      Line 1           — {"type": "run_start", ...metadata...}
      Lines 2 .. N+1   — {"type": "result", ...audit fields...}   (one per question)
      Last line        — {"type": "run_summary", ...totals...}     (only if completed)
    """
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    report_path = REPORT_DIR / f"report_{timestamp}.jsonl"

    _jsonl_append(report_path, {
        "type": "run_start",
        "timestamp": timestamp,
        "workspace_id_override": EVAL_WORKSPACE_ID,
        "top_k": top_k,
        "recall_page_tolerance": _RECALL_PAGE_TOLERANCE,
    })
    return report_path


def _append_result(report_path: Path, audit: Dict) -> None:
    """Flush one question result to the JSONL file immediately after scoring."""
    _jsonl_append(report_path, {"type": "result", **audit})


def _finalize_report(report_path: Path, all_results: List[EvalResult]) -> None:
    """Append a summary line at the end of a completed run."""
    if not all_results:
        return
    overall_recall = sum(r.recall for r in all_results) / len(all_results) * 100
    overall_accuracy = sum(r.accuracy for r in all_results) / len(all_results) * 100
    _jsonl_append(report_path, {
        "type": "run_summary",
        "total_questions": len(all_results),
        "overall_recall_pct": round(overall_recall, 2),
        "overall_accuracy_pct": round(overall_accuracy, 2),
    })


def _jsonl_append(path: Path, entry: Dict) -> None:
    """Append one JSON object as a newline to *path* (creates the file if absent)."""
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Console summary
# ---------------------------------------------------------------------------

_W = 68  # interior width of the summary box


def _bar(pct: float, width: int = 28) -> str:
    """ASCII progress bar: '████████░░░░░░  57.1%'."""
    filled = round(pct / 100 * width)
    return "█" * filled + "░" * (width - filled) + f"  {pct:5.1f}%"


def _print_summary(rows: list, all_results: List[EvalResult]) -> None:
    headers = ["Document", "N", "Page Recall (±2)", "Semantic Accuracy", "Time"]
    print("\n" + tabulate(rows, headers=headers, tablefmt="rounded_grid"))

    if not all_results:
        return

    overall_recall = sum(r.recall for r in all_results) / len(all_results) * 100
    overall_accuracy = sum(r.accuracy for r in all_results) / len(all_results) * 100
    n = len(all_results)

    border = "═" * _W
    print(f"\n  ╔{border}╗")
    print(f"  ║{'EVALUATION SUMMARY':^{_W}}║")
    print(f"  ╠{border}╣")
    print(f"  ║  {'Total questions evaluated:':<28} {n:>4}{'':>{_W - 34}}║")
    print(f"  ╠{border}╣")

    recall_bar = _bar(overall_recall)
    recall_label = "  Page Recall  (±2 pages)   "
    print(f"  ║  {recall_label}{recall_bar:<{_W - len(recall_label) - 2}}║")

    print(f"  ╠{border}╣")

    acc_bar = _bar(overall_accuracy)
    acc_label = "  Semantic Accuracy (LLM)   "
    print(f"  ║  {acc_label}{acc_bar:<{_W - len(acc_label) - 2}}║")
    print(f"  ╚{border}╝\n")
