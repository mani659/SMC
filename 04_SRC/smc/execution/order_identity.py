"""Book/tag order identity (parallel dedicated confirmation books — SPIKE).

Design: ``06_RESEARCH/PARALLEL_DEDICATED_PATH_DESIGN.md`` §3.4 (magic/comment
identity, ruling R-D). The spike needs a statement line to name the book that
placed it, WITHOUT changing any existing order text.

Rules implemented here (pure functions, no MT5, no strategy):

* A candidate that carries a ``product_menu.book_id`` stamp from a NON-production
  book gets its comment prefixed ``SMC-<TAG>-`` (the tag is the book's trigger
  letter). The prefix is truncated to the MT5 comment limit so the identity
  survives the broker's field width.
* A candidate with no book stamp, or one stamped with the production book
  (``PROD``), keeps its comment EXACTLY as before. Default behaviour is
  therefore byte-identical to today's single-menu path.
* ``book_magic`` is the deterministic per-book offset proposed by the design
  (``base + book_index``). It is NOT wired into any live default: changing
  magic changes statement/EA expectations, which stays an architect ruling.
"""

from __future__ import annotations

import json

__all__ = [
    "BOOK_COMMENT_PREFIX",
    "PRODUCTION_BOOK_ID",
    "MT5_COMMENT_MAX",
    "book_identity",
    "book_comment",
    "book_magic",
]

#: Comment namespace for parallel-book orders (MT5 comments are plain text).
BOOK_COMMENT_PREFIX = "SMC"

#: The production (single-menu) book id — its orders keep today's comment.
PRODUCTION_BOOK_ID = "PROD"

#: MT5 truncates order comments at 31 characters; identity must fit.
MT5_COMMENT_MAX = 31


def _menu_stamp(candidate) -> dict:
    """The ``product_menu`` stamp of a candidate (empty dict when absent)."""
    raw = getattr(candidate, "signal_data_json", None)
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    if not isinstance(payload, dict):
        return {}
    found = payload.get("product_menu")
    return found if isinstance(found, dict) else {}


def book_identity(candidate) -> tuple[str | None, str | None]:
    """``(book_id, book_tag)`` from the candidate's menu stamp (None = absent).

    Unknown stays unknown — a candidate without a stamp is never guessed into
    a book.
    """
    stamp = _menu_stamp(candidate)
    book_id = stamp.get("book_id")
    tag = stamp.get("book_tag")
    return (
        str(book_id) if book_id else None,
        str(tag) if tag else None,
    )


def book_comment(candidate, base_comment: str = "") -> str:
    """Order comment carrying the book identity (default path unchanged).

    ``PROD`` / unstamped candidates return ``base_comment`` verbatim, so the
    production statement text is identical to today's. A dedicated book gets
    ``SMC-<TAG>-<base>`` truncated to the MT5 comment width, keeping the
    prefix (the identity part) intact.
    """
    base = str(base_comment or "")
    book_id, tag = book_identity(candidate)
    if not book_id or book_id == PRODUCTION_BOOK_ID:
        return base
    label = tag or book_id
    prefix = f"{BOOK_COMMENT_PREFIX}-{label}"
    text = f"{prefix}-{base}" if base else prefix
    return text[:MT5_COMMENT_MAX]


def book_magic(base_magic: int, book_index: int) -> int:
    """Deterministic per-book magic offset (design §3.4, ruling R-D).

    ``base + index`` with index 0 reserved for the production book, so a
    single-book deployment is exactly ``base_magic``. Nothing in the live
    default calls this yet — the spike only proves the mapping.
    """
    if int(book_index) < 0:
        raise ValueError("book_index must be >= 0")
    return int(base_magic) + int(book_index)
