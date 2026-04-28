from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from loguru import logger

from app.models import EvalResult, GoldenQuestion
from app.rag import generator
from app.retrieval import search as retrieval_search

# Hebrew phrases that indicate a correct "not found" refusal from the LLM.
# Includes the exact system-prompt phrase plus the task-specified variants.
_REFUSAL_PHRASES = [
    "המידע המבוקש לא נמצא במסמכים שסופקו",  # exact system-prompt phrase
    "לא נמצא מידע",
    "אינו מופיע במקורות",
]

DEFAULT_DATASET = Path("data/golden_set.json")
_SEP = "=" * 60


class RAGEvaluator:
    """Evaluate retrieval and faithfulness quality against a golden dataset.

    The dataset is a JSON array of GoldenQuestion objects:
        [
          {"query": "...", "query_type": "in_context",
           "expected_doc_id": "abc", "expected_page": 3},
          {"query": "...", "query_type": "out_of_context"}
        ]

    Metrics:
        Recall@K  — whether the expected page/doc appears in the top-K chunks.
        Faithfulness — whether the LLM correctly refuses out-of-context queries.
    """

    def __init__(self, top_k: int = 5) -> None:
        self.top_k = top_k

    # ------------------------------------------------------------------
    # Metric helpers
    # ------------------------------------------------------------------

    def _check_recall(self, question: GoldenQuestion, results: list) -> bool:
        """True if any retrieved chunk matches the expected doc+page."""
        for r in results:
            page_ok = question.expected_page is None or r.page_num == question.expected_page
            doc_ok = question.expected_doc_id is None or r.document_id == question.expected_doc_id
            if page_ok and doc_ok:
                return True
        return False

    def _check_faithfulness(self, answer: str) -> bool:
        """True if the LLM answer contains a known Hebrew refusal phrase."""
        return any(phrase in answer for phrase in _REFUSAL_PHRASES)

    # ------------------------------------------------------------------
    # Per-question evaluation
    # ------------------------------------------------------------------

    def _evaluate_one(self, question: GoldenQuestion) -> EvalResult:
        logger.info(
            "  Evaluating [{}] {!r}",
            question.query_type,
            question.query[:60],
        )

        results = retrieval_search.search(question.query, top_k=self.top_k)

        recall_hit: Optional[bool] = None
        faithfulness_pass: Optional[bool] = None
        answer = ""

        if question.query_type == "in_context" and question.expected_page is not None:
            recall_hit = self._check_recall(question, results)
            logger.debug("    Recall@{}: {}", self.top_k, "HIT" if recall_hit else "MISS")

        if question.query_type == "out_of_context":
            try:
                rag_response = generator.generate(question.query, results)
                answer = rag_response.answer
                faithfulness_pass = self._check_faithfulness(answer)
                logger.debug(
                    "    Faithfulness: {}",
                    "PASS" if faithfulness_pass else "FAIL",
                )
            except Exception as exc:
                logger.warning("    LLM call failed for faithfulness check: {}", exc)

        return EvalResult(
            query=question.query,
            query_type=question.query_type,
            recall_hit=recall_hit,
            faithfulness_pass=faithfulness_pass,
            answer=answer,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_suite(self, dataset_path: Path | str = DEFAULT_DATASET) -> List[EvalResult]:
        """Load *dataset_path*, run every question, and print a summary report.

        Returns the list of EvalResult objects for programmatic inspection.
        Raises FileNotFoundError if the dataset file does not exist.
        """
        path = Path(dataset_path)
        if not path.exists():
            raise FileNotFoundError(f"Golden dataset not found: {path}")

        items = json.loads(path.read_text(encoding="utf-8"))
        questions = [GoldenQuestion(**item) for item in items]
        logger.info(
            "Evaluation suite start: {} questions  top_k={}",
            len(questions),
            self.top_k,
        )

        results: List[EvalResult] = []
        for q in questions:
            results.append(self._evaluate_one(q))

        self._print_report(results)
        return results

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------

    def _print_report(self, results: List[EvalResult]) -> None:
        in_ctx = [r for r in results if r.query_type == "in_context" and r.recall_hit is not None]
        out_ctx = [
            r for r in results
            if r.query_type == "out_of_context" and r.faithfulness_pass is not None
        ]

        recall_hits = sum(1 for r in in_ctx if r.recall_hit)
        faith_passes = sum(1 for r in out_ctx if r.faithfulness_pass)

        recall_pct = recall_hits / len(in_ctx) * 100 if in_ctx else 0.0
        faith_pct = faith_passes / len(out_ctx) * 100 if out_ctx else 0.0

        logger.info(_SEP)
        logger.info("  RAG EVALUATION REPORT")
        logger.info(_SEP)
        logger.info("  Total questions    : {}", len(results))
        logger.info("  In-context         : {}", len(in_ctx))
        logger.info("  Out-of-context     : {}", len(out_ctx))
        logger.info(_SEP)
        logger.info(
            "  Recall@{}           : {}/{} ({:.1f}%)",
            self.top_k, recall_hits, len(in_ctx), recall_pct,
        )
        logger.info(
            "  Faithfulness       : {}/{} ({:.1f}%)",
            faith_passes, len(out_ctx), faith_pct,
        )
        logger.info(_SEP)

        for i, r in enumerate(results, 1):
            if r.query_type == "in_context":
                mark = "✓" if r.recall_hit else "✗"
                tag = "Recall@{}={}".format(self.top_k, mark)
            else:
                mark = "✓" if r.faithfulness_pass else "✗"
                tag = "Faithful={}".format(mark)
            logger.info("  [{:>2}] {}  {}", i, tag, r.query[:55])

        logger.info(_SEP)
