#!/usr/bin/env python3
"""Lint AGENTS.md files: enforce the agreed structure.

Rules:
1. File must start with a `# <name>` heading.
2. Must contain a "Rules" or "Public API" section (apps vs libs).
3. Must be <= 200 lines (progressive disclosure principle).
4. Must reference `make` for commands, not raw tool names.
5. App AGENTS.md must have ## Inputs and ## Outputs sections.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

MAX_LINES = 200


def lint(path: Path) -> list[str]:
    text = path.read_text()
    lines = text.splitlines()
    errs: list[str] = []

    if not lines or not lines[0].startswith("# "):
        errs.append(f"{path}: must start with `# <name>` heading")

    if len(lines) > MAX_LINES:
        errs.append(
            f"{path}: too long ({len(lines)} > {MAX_LINES} lines) — split into subdirectories"
        )

    lower = text.lower()
    if "rules" not in lower and "public api" not in lower:
        errs.append(f"{path}: must contain a `Rules` or `Public API` section")

    # Forbid raw command invocations that bypass Makefile (common drift signal).
    forbidden = ["databricks bundle deploy", "uv run pytest", "sbt clean"]
    for line in lines:
        for f in forbidden:
            if f in line and "make " not in line and "<!-- raw-ok -->" not in line:
                errs.append(f"{path}:{lines.index(line) + 1}: prefer `make` over raw `{f}`")

    # App AGENTS.md must declare Inputs and Outputs for data-map generation.
    is_app = re.search(r"[/\\]apps[/\\][^/\\]+[/\\]AGENTS\.md$", str(path))
    if is_app:
        headers = [h.strip().lower() for h in re.findall(r"^## (.+)$", text, re.MULTILINE)]
        if "inputs" not in headers:
            errs.append(f"{path}: app AGENTS.md must have a `## Inputs` section")
        if "outputs" not in headers:
            errs.append(f"{path}: app AGENTS.md must have a `## Outputs` section")

    return errs


def main(args: list[str]) -> int:
    errs: list[str] = []
    for a in args:
        errs.extend(lint(Path(a)))
    if errs:
        print("\n".join(errs), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
