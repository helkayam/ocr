#!/usr/bin/env python3
"""ProtocolGenesis OCR — synchronous MVP CLI.

Usage examples:
    python main.py ingest path/to/document.pdf
    python main.py ask "מה נושאי הישיבה?"
    python main.py ask "מה נושאי הישיבה?" --top-k 10
    python main.py delete <doc_id>
    python main.py reindex <doc_id>
    python main.py --debug ingest path/to/document.pdf
"""
from __future__ import annotations

import sys

import click
from loguru import logger


# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------

def _configure_logging(debug: bool) -> None:
    logger.remove()
    if debug:
        logger.add(
            sys.stderr,
            level="DEBUG",
            format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | "
                   "<cyan>{name}</cyan>:<cyan>{line}</cyan> | {message}",
            colorize=True,
        )
    else:
        logger.add(
            sys.stderr,
            level="INFO",
            format="<level>{level: <8}</level> | {message}",
            colorize=True,
        )


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------

@click.group()
@click.option(
    "--debug",
    is_flag=True,
    default=False,
    help="Show full tracebacks and DEBUG-level logs on error.",
)
@click.pass_context
def cli(ctx: click.Context, debug: bool) -> None:
    """ProtocolGenesis OCR — Hebrew-optimised document RAG system."""
    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug
    _configure_logging(debug)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _handle_error(ctx: click.Context, exc: Exception, hint: str) -> None:
    """Print a user-friendly error or re-raise for full traceback in debug mode."""
    if ctx.obj.get("debug"):
        raise exc
    logger.error("{}: {}", hint, exc)
    sys.exit(1)


def _separator() -> None:
    click.echo("─" * 60)


# ---------------------------------------------------------------------------
# ingest
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("path", type=click.Path(exists=True, dir_okay=False))
@click.pass_context
def ingest(ctx: click.Context, path: str) -> None:
    """Ingest a PDF through OCR → chunking → indexing (Phases 2-5)."""
    from app.pipeline import ingest_pipeline

    try:
        doc_id = ingest_pipeline(path)
    except Exception as exc:
        _handle_error(ctx, exc, "Ingest failed")
        return

    _separator()
    click.echo(click.style(" Ingest complete", fg="green", bold=True))
    click.echo(f"  document_id : {doc_id}")
    click.echo(f"  source file : {path}")
    _separator()


# ---------------------------------------------------------------------------
# ask
# ---------------------------------------------------------------------------

@cli.command("ask")
@click.argument("query")
@click.option(
    "--top-k",
    default=5,
    show_default=True,
    type=click.IntRange(1, 50),
    help="Number of context chunks to retrieve from the vector DB.",
)
@click.pass_context
def ask_cmd(ctx: click.Context, query: str, top_k: int) -> None:
    """Ask a question and receive a Hebrew answer with source citations."""
    from app.pipeline import ask_pipeline

    try:
        response = ask_pipeline(query, top_k=top_k)
    except Exception as exc:
        _handle_error(ctx, exc, "Query failed")
        return

    _separator()
    click.echo(click.style(" Answer", fg="cyan", bold=True))
    _separator()
    click.echo(response.answer)
    _separator()

    if response.sources:
        click.echo(click.style(" Sources", fg="yellow", bold=True))
        seen: set[tuple] = set()
        for s in response.sources:
            key = (s.document_id, s.page_num)
            if key not in seen:
                click.echo(f"  • {s.document_id}  (page {s.page_num})")
                seen.add(key)
    else:
        click.echo(click.style(" Sources: none", fg="yellow"))

    _separator()


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("doc_id")
@click.pass_context
def delete(ctx: click.Context, doc_id: str) -> None:
    """Fully remove a document from the registry, data files, and vector DB."""
    from app.pipeline import delete_pipeline

    try:
        delete_pipeline(doc_id)
    except KeyError as exc:
        _handle_error(ctx, exc, "Document not found")
        return
    except Exception as exc:
        _handle_error(ctx, exc, "Delete failed")
        return

    _separator()
    click.echo(click.style(" Delete complete", fg="green", bold=True))
    click.echo(f"  document_id : {doc_id}")
    _separator()


# ---------------------------------------------------------------------------
# reindex
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("doc_id")
@click.pass_context
def reindex(ctx: click.Context, doc_id: str) -> None:
    """Delete vectors and re-run Phase 5 indexing for an existing document."""
    from app.pipeline import reindex_pipeline

    try:
        count = reindex_pipeline(doc_id)
    except (KeyError, FileNotFoundError) as exc:
        _handle_error(ctx, exc, "Reindex failed")
        return
    except Exception as exc:
        _handle_error(ctx, exc, "Reindex failed")
        return

    _separator()
    click.echo(click.style(" Reindex complete", fg="green", bold=True))
    click.echo(f"  document_id : {doc_id}")
    click.echo(f"  vectors     : {count}")
    _separator()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli()
