"""RQ worker entry point.

Run with:
    python -m app.worker.main
or directly via the RQ CLI:
    rq worker ocr --url redis://localhost:6379
"""
from __future__ import annotations

import os
import sys

from loguru import logger
from redis import Redis
from rq import Queue, Worker

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
QUEUE_NAME = "ocr"


def _configure_logging() -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        level="INFO",
        format="<level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> | {message}",
        colorize=True,
    )


def main() -> None:
    _configure_logging()
    conn = Redis.from_url(REDIS_URL)
    q = Queue(QUEUE_NAME, connection=conn)
    logger.info("Worker: listening on queue={!r} redis={}", QUEUE_NAME, REDIS_URL)
    worker = Worker([q], connection=conn)
    worker.work()


if __name__ == "__main__":
    main()
