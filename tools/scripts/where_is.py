#!/usr/bin/env python3
"""Find a dbt model — where it lives, what depends on it.

Reads two signals:
1. Filesystem scan (cheap, always works).
2. dbt manifest.json after `dbt parse` (authoritative, includes deps).

Usage:
    uv run python tools/scripts/where_is.py <model_name>
    just where-is <model_name>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def find_in_files(name: str) -> list[dict]:
    """Signal 2: filesystem scan under dbt/*/models/."""
    hits: list[dict] = []
    for sql in REPO_ROOT.glob(f"dbt/*/models/**/{name}.sql"):
        parts = sql.relative_to(REPO_ROOT).parts
        project = parts[1] if len(parts) > 1 else None
        hits.append({
            "project": project,
            "path": str(sql.relative_to(REPO_ROOT)),
        })
    return hits


def find_in_manifest(name: str) -> list[dict]:
    """Signal 1: dbt manifest, if any project has parsed."""
    out: list[dict] = []
    for manifest in REPO_ROOT.glob("dbt/*/target/manifest.json"):
        try:
            data = json.loads(manifest.read_text())
        except Exception:
            continue
        nodes = data.get("nodes", {})
        child_map = data.get("child_map", {})
        for node_id, node in nodes.items():
            if node.get("name") != name:
                continue
            out.append({
                "node_id": node_id,
                "project": node.get("package_name"),
                "path": node.get("path"),
                "access": node.get("access"),
                "materialized": (node.get("config") or {}).get("materialized"),
                "contract_enforced": ((node.get("config") or {}).get("contract") or {}).get("enforced"),
                "meta_classification": (node.get("meta") or {}).get("classification"),
                "meta_pii": (node.get("meta") or {}).get("pii"),
                "depends_on": (node.get("depends_on") or {}).get("nodes", []),
                "consumed_by": child_map.get(node_id, []),
            })
    return out


def find_app_consumers(name: str) -> list[str]:
    """Signal 5: grep data-architecture.md for app-side references.

    Returns app names that explicitly read this model per the consumer matrix.
    """
    doc = REPO_ROOT / "docs" / "data-architecture.md"
    if not doc.exists():
        return []
    text = doc.read_text()
    consumers: list[str] = []
    for line in text.splitlines():
        if name in line and "apps/" in line:
            # crude match — line in the consumer matrix mentioning this model
            for token in line.split("`"):
                if token.startswith("apps/"):
                    consumers.append(token)
    return sorted(set(consumers))


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: where_is.py <model_name>", file=sys.stderr)
        return 1
    name = sys.argv[1]
    result = {
        "model": name,
        "file_hits": find_in_files(name),
        "manifest_hits": find_in_manifest(name),
        "app_consumers_per_docs": find_app_consumers(name),
    }
    if not result["file_hits"] and not result["manifest_hits"]:
        print(f"No dbt model named '{name}' found in this repo.", file=sys.stderr)
        print("Tip: run `dbt parse` inside the suspected project for manifest-level search.", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
