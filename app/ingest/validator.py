from __future__ import annotations

from pathlib import Path

from loguru import logger

_PDF_MAGIC = b"%PDF"
_MAX_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB


def validate_pdf(path: Path) -> None:
    """Raise an appropriate exception if *path* is not an ingestable PDF.

    Checks (in order):
      1. Path exists and is a regular file.
      2. File is not empty and does not exceed the size cap.
      3. File starts with the PDF magic bytes (%PDF).
    """
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if not path.is_file():
        raise ValueError(f"Path is not a regular file: {path}")

    size = path.stat().st_size
    if size == 0:
        raise ValueError(f"File is empty: {path}")
    if size > _MAX_SIZE_BYTES:
        raise ValueError(
            f"File size {size} bytes exceeds limit of {_MAX_SIZE_BYTES} bytes: {path}"
        )

    with path.open("rb") as fh:
        header = fh.read(4)
    if header != _PDF_MAGIC:
        raise ValueError(
            f"File does not appear to be a PDF (magic bytes: {header!r}): {path}"
        )

    logger.debug("Validation passed: {}", path)
