"""Text normalisation helpers (pure infrastructure — no domain knowledge)."""

from __future__ import annotations

import unicodedata

# ``đ``/``Đ`` is a distinct letter, not a base + combining mark, so NFD leaves it
# untouched and stripping marks alone would never make "duc" match "Đức".
_EXTRA_FOLDS = str.maketrans({"đ": "d", "Đ": "d", "Ð": "d"})


def normalize_search(value: str | None) -> str:
    """Fold a string to a diacritic-free, case-insensitive search key.

    Applied to **both** sides of a comparison so a Vietnamese name matches what a
    user types on an unaccented keyboard: ``normalize_search("Thành Đức")`` is
    ``"thanh duc"``, which ``"duc"`` is a substring of. Mirrors the frontend's
    ``normalizeText`` in ``src/lib/text.ts`` — keep the two in step.
    """
    if not value:
        return ""
    folded = value.translate(_EXTRA_FOLDS)
    decomposed = unicodedata.normalize("NFD", folded)
    without_marks = "".join(c for c in decomposed if not unicodedata.combining(c))
    return without_marks.casefold().strip()
