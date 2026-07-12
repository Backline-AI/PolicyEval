#!/usr/bin/env python3
"""Verify that relative Markdown links resolve to existing files.

Scans README.md and every Markdown file under docs/. External links
(http/https/mailto) and pure in-page anchors (#section) are skipped.
Relative links are resolved against the directory of the file that
contains them. Exits non-zero if any link is broken.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# [text](target) — capture the target, then strip any trailing #anchor.
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")

ROOT = Path(__file__).resolve().parent.parent


def markdown_files() -> list[Path]:
    files = [ROOT / "README.md"]
    files.extend(sorted((ROOT / "docs").rglob("*.md")))
    return [f for f in files if f.is_file()]


def is_external(target: str) -> bool:
    return target.startswith(("http://", "https://", "mailto:", "#"))


def check_file(md: Path) -> list[str]:
    broken: list[str] = []
    for match in LINK_RE.finditer(md.read_text(encoding="utf-8")):
        target = match.group(1).strip()
        if is_external(target):
            continue
        path_part = target.split("#", 1)[0]
        if not path_part:  # link was a bare anchor like (#foo)
            continue
        resolved = (md.parent / path_part).resolve()
        if not resolved.exists():
            broken.append(f"{md.relative_to(ROOT)} -> {target}")
    return broken


def main() -> int:
    broken: list[str] = []
    for md in markdown_files():
        broken.extend(check_file(md))

    if broken:
        print("Broken links found:")
        for entry in broken:
            print(f"  {entry}")
        return 1

    print("All Markdown links resolve.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
