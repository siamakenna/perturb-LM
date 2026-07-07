from __future__ import annotations

from pathlib import Path

BANNED_UNQUALIFIED_CLAIMS = [
    "biological retrieval achieved",
    "proves biological retrieval",
    "proves biological image understanding",
    "discovers biology",
    "solves biological search",
    "validated biological retrieval",
]
NEGATING_CONTEXTS = [
    "not ",
    "does not ",
    "do not ",
    "neither ",
    "without ",
    "no ",
]


def test_public_docs_do_not_make_unqualified_biological_claims() -> None:
    public_paths = [
        *Path("docs").glob("*.md"),
        Path("README.md"),
        Path("site/index.html"),
    ]
    for path in public_paths:
        text = path.read_text(errors="ignore").lower()
        for banned in BANNED_UNQUALIFIED_CLAIMS:
            for index in _find_all(text, banned):
                context = text[max(0, index - 32) : index]
                assert any(negator in context for negator in NEGATING_CONTEXTS), (
                    f"Unqualified claim found in {path}: {banned}"
                )


def _find_all(text: str, needle: str) -> list[int]:
    indexes: list[int] = []
    start = 0
    while True:
        index = text.find(needle, start)
        if index < 0:
            return indexes
        indexes.append(index)
        start = index + 1
