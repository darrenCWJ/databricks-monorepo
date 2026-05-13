#!/usr/bin/env python3
"""Compare outputs of a migrated DAB against the legacy script.

Used during the shadow-write phase of migration. Compares two Unity Catalog
tables (legacy vs migrated) on row count, schema, key hash distribution, and
a configurable set of business-metric aggregates.

Usage:
    uv run python tools/scripts/diff_outputs.py \
        --bundle apps/customer360-etl \
        --legacy cdo_dev.legacy.customer_360 \
        --new    cdo_dev.silver.customer_360 \
        --key customer_id

Fails (exit 1) if any check exceeds the configured tolerance.
"""
from __future__ import annotations

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", required=True, help="DAB directory (for tolerance config lookup)")
    parser.add_argument("--legacy", required=True, help="Legacy table FQN")
    parser.add_argument("--new", required=True, help="New table FQN")
    parser.add_argument("--key", required=True, help="Primary key column")
    parser.add_argument("--row-count-tolerance", type=float, default=0.001,
                        help="Acceptable row-count delta (fraction).")
    args = parser.parse_args()

    # This script is intended to run on a Databricks cluster (or via dbsql).
    # For the scaffold we sketch the structure; wire it up against your auth.
    print(f"Comparing legacy={args.legacy} vs new={args.new} on key={args.key}")
    print("TODO: implement against Databricks SQL or dbx connect.")
    print("Suggested checks:")
    print("  1. Row counts match within tolerance")
    print("  2. Schemas match (column names + types)")
    print("  3. Hash of sorted PKs matches")
    print("  4. Per-column null rates within tolerance")
    print("  5. Business-metric aggregates (sum/avg) within tolerance")
    print("Exit 1 if any check fails.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
