#!/usr/bin/env python3
"""Quarterly access review: dump CODEOWNERS + Databricks workspace ACLs +
Unity Catalog grants to CSV for governance review.

Usage:
    uv run python tools/scripts/dump_access.py --target prod --out reviews/
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def parse_codeowners() -> list[tuple[str, str]]:
    """Return list of (path_glob, owner) tuples from CODEOWNERS."""
    rows: list[tuple[str, str]] = []
    f = REPO_ROOT / "CODEOWNERS"
    if not f.exists():
        return rows
    for line in f.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            rows.append((parts[0], " ".join(parts[1:])))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True)
    parser.add_argument("--out", default="reviews/")
    args = parser.parse_args()

    date = dt.date.today().isoformat()
    out_dir = REPO_ROOT / args.out / date
    out_dir.mkdir(parents=True, exist_ok=True)

    with (out_dir / "codeowners.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["path", "owners"])
        for r in parse_codeowners():
            w.writerow(r)

    # TODO: hook up to Databricks SDK for workspace ACLs + UC grants
    # databricks api workspace/list, unity-catalog grants list, etc.
    print(f"Access dump written to {out_dir}")
    print("TODO: add Databricks ACL + UC grant export against target", args.target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
