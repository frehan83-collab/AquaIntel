"""Document integrity — the brief has to stay readable (WS-60).

`docs/HANDOVER.md` is the takeover brief: the first file the next coding module
reads, and the one an owner skims before a demo. On 2026-10-21 it was found to
hold **1,429 lines that reconstruct to 1,389 characters** — an earlier draft of
the WS-39/40 section written one character per line (1,389 single-character
lines plus 40 blank separators) — immediately in front of the clean copy of the
same section. The same file carried **26 runs of cp1252 mojibake** (18 arrows,
3 minus signs, 3 ø, one ≥, one ×), and `CLAUDE.md` quoted a truncated sample
that could no longer be decoded. The exploded copy made §5 unreadable between
WS-29 and WS-39/40, and the duplicate heading let a reader quote stale wording.
No test read the documents, so nothing noticed for three days.

These tests do. They are about *shape*, not wording: they fail when a document
stops being a document, and they never pin prose. Two honest limits: damage
shorter than 20 consecutive near-empty lines is not caught (ordinary markdown
does contain short lines), and only markdown the reader lands on — the repo root
and `docs/` — is covered.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# The documents a reader lands on: the repo root and docs/. Frontend, memory and
# .claude notes are deliberately out of scope (not reader-facing, and a skills
# file may legitimately quote broken text).
DOC_FILES = sorted(
    {*ROOT.glob("*.md"), *ROOT.glob("docs/*.md"), *ROOT.glob("docs/**/*.md")}
)

# A run of characters a cp1252 round-trip can produce. The class starts at
# U+0080 because a mojibake run's trailing byte often lands in the cp1252 high
# half (ø arrived as U+00C3 U+00B8). Only runs that actually decode are damage.
MOJIBAKE_RUN = re.compile(
    r"[\u0080-\u00ff\u0152\u0153\u0160\u0161\u0178\u017d\u017e\u0192"
    r"\u02c6\u02dc\u2013\u2014\u2018\u2019\u201a\u201c\u201d\u201e"
    r"\u2020\u2021\u2022\u2026\u2030\u2039\u203a\u20ac\u2122]{2,}"
)

# An exploded line leaves this behind: many consecutive lines of <= 2 characters.
# Ordinary markdown never produces 20 in a row (a bullet is "- ", a table row
# carries content, and a separator row is longer).
EXPLOSION_RUN = 20
EXPLOSION_WIDTH = 2


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def _exploded_runs(text: str) -> list[tuple[int, int]]:
    """(first_line, last_line) of each run of near-empty lines, 1-based."""
    lines = text.split("\n")
    runs: list[tuple[int, int]] = []
    start = 0
    for number, line in enumerate(lines, start=1):
        if len(line.strip()) <= EXPLOSION_WIDTH:
            if not start:
                start = number
        elif start:
            if number - start >= EXPLOSION_RUN:
                runs.append((start, number - 1))
            start = 0
    if start and len(lines) - start + 1 >= EXPLOSION_RUN:
        runs.append((start, len(lines)))
    return runs


def _decode(run: str) -> str | None:
    """The intended text of a damaged run, or None when it is genuine text."""
    try:
        fixed = run.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return None
    return fixed if fixed != run else None


def _repaired(piece: str) -> tuple[str, str] | None:
    """(damaged slice, intended text) for one run, or None if it is clean.

    A run can begin or end with a genuine character - a Norwegian word glued to
    double-encoded punctuation - and then the whole run will not decode. Retry
    it trimmed by up to two characters at each end.
    """
    fixed = _decode(piece)
    if fixed:
        return piece, fixed
    for left in range(1, 3):
        for right in range(0, 3):
            inner = piece[left:len(piece) - right] if right else piece[left:]
            if len(inner) < 2:
                continue
            fixed = _decode(inner)
            if fixed:
                return inner, fixed
    return None


def _mojibake(text: str) -> list[tuple[int, str, str]]:
    """(line, damaged slice, intended text) for each reversible cp1252 run."""
    found: list[tuple[int, str, str]] = []
    for match in MOJIBAKE_RUN.finditer(text):
        hit = _repaired(match.group(0))
        if hit:
            line = text.count("\n", 0, match.start()) + 1
            found.append((line, hit[0], hit[1]))
    return found


@pytest.mark.parametrize("path", DOC_FILES, ids=_rel)
def test_document_is_not_exploded(path: Path) -> None:
    runs = _exploded_runs(_read(path))
    assert not runs, (
        f"{_rel(path)}: {len(runs)} run(s) of >= {EXPLOSION_RUN} near-empty "
        f"lines, first at line {runs[0][0]}-{runs[0][1]}. A line was written "
        "one character per line (a '\\n'.join() of a string). Re-join the run, "
        "or delete the block if it duplicates a later section."
    )


@pytest.mark.parametrize("path", DOC_FILES, ids=_rel)
def test_document_has_no_mojibake(path: Path) -> None:
    found = _mojibake(_read(path))
    assert not found, (
        f"{_rel(path)}: {len(found)} mojibake run(s), first at line "
        f"{found[0][0]}: {found[0][1]!r} should read {found[0][2]!r}. The file "
        "went through a cp1252 round-trip; re-encode it as UTF-8."
    )


def test_handover_lists_each_workstream_once() -> None:
    """A duplicated section lets a reader quote superseded wording."""
    lines = _read(ROOT / "docs" / "HANDOVER.md").split("\n")
    headings = [line.strip() for line in lines if line.startswith("### ")]
    seen: dict[str, int] = {}
    duplicates: list[str] = []
    for heading in headings:
        key = re.split(r"\s+[-\u2014\u00b7]\s+", heading)[0]
        if key in seen:
            duplicates.append(heading)
        seen[key] = seen.get(key, 0) + 1
    assert not duplicates, (
        "docs/HANDOVER.md repeats workstream heading(s): "
        + "; ".join(duplicates)
        + ". Keep one section and delete the stale copy."
    )


def test_readme_counts_match_the_tree() -> None:
    """The README is the first page a buyer reads, and its counts were 7 months stale.

    On 2026-10-21 it still advertised 66 engines, 59 pages, 432 tests and 303 API
    routes against a measured 82 / 46 / 1,653 / 354. Counts are recomputed here,
    so the page cannot drift again; a typed *test* count is refused outright
    because it goes stale the day it is written.
    """
    readme = _read(ROOT / "README.md")
    engines = len(
        [p for p in (ROOT / "core" / "market").glob("*.py") if p.name != "__init__.py"]
    )
    app = ROOT / "frontend" / "src" / "app"
    routes = [p for p in app.rglob("page.tsx") if p.parent != app]
    paths = len(json.loads(_read(ROOT / "docs" / "openapi.frozen.json"))["paths"])

    assert f"**{engines} engines**" in readme, (
        f"README.md should say **{engines} engines** (core/market/*.py)"
    )
    assert f"**{len(routes)} page routes**" in readme, (
        f"README.md should say **{len(routes)} page routes** "
        f"(page.tsx files under frontend/src/app, excluding the root dashboard)"
    )
    assert f"**{paths} API paths**" in readme, (
        f"README.md should say **{paths} API paths** (docs/openapi.frozen.json)"
    )
    assert not re.search(r"\b\d[\d,]*\s+tests\b", readme), (
        "README.md types a test count, which goes stale the day it is written; "
        "say 'full suite green' and point at PROJECT_STATUS.md instead"
    )


def test_detectors_find_the_damage_they_were_written_for() -> None:
    """A ratchet that cannot fail is decoration - prove each detector fires."""
    # the shape found in HANDOVER on 2026-10-21: one character per line
    heading = "### WS-39/40 - a heading"
    assert _exploded_runs("\n".join(heading)) == [(1, len(heading))]
    assert _exploded_runs("\n".join("ab" for _ in range(25)))
    # the 26 runs: an arrow, a minus sign, ø, a ≥ and a multiplication sign
    assert _mojibake("goal \u00e2\u2020\u2019 files")
    assert _mojibake("feed \u00e2\u02c6\u2019 29.39")
    assert _mojibake("Ler\u00c3\u00b8y")
    assert _mojibake("n \u00e2\u2030\u00a5 5")
    assert _mojibake("localities \u00c3\u2014 800")
    # glued to real text: the whole run will not decode, the inner slice does
    assert _mojibake("bl\u00e5\u00e2\u20ac\u201cgr\u00c3\u00b8nn")
    # genuine Norwegian and ordinary punctuation must never be flagged
    assert not _mojibake("Ler\u00f8y, Sj\u00f8kart, Nord-Tr\u00f8ndelag, \u00e5")
    assert not _mojibake("price - cost \u00b7 margin \u2265 0")
    assert not _exploded_runs("| a | b |\n|---|---|\n| 1 | 2 |\n")
