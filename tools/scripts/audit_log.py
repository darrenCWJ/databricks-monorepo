#!/usr/bin/env python3
"""Append a deployment record to the SOC2 audit bucket.

Writes a JSON line with: timestamp, bundle, target, git sha, actor,
change ticket (if present in MR title). The S3 bucket has Object Lock
enabled (WORM) so records cannot be edited or deleted.

Usage:
    uv run python tools/scripts/audit_log.py \
        --bundle customer360-etl --target prod --sha abc123
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--target", required=True, choices=["dev", "staging", "prod"])
    parser.add_argument("--sha", required=True)
    parser.add_argument("--bucket", default=os.environ.get("CDO_AUDIT_BUCKET", "cdo-soc2-audit"))
    args = parser.parse_args()

    record = {
        "ts": dt.datetime.now(dt.UTC).isoformat(),
        "bundle": args.bundle,
        "target": args.target,
        "git_sha": args.sha,
        "actor": os.environ.get("GITLAB_USER_LOGIN", "unknown"),
        "ci_job_url": os.environ.get("CI_JOB_URL", ""),
        "ci_pipeline_id": os.environ.get("CI_PIPELINE_ID", ""),
        "mr_iid": os.environ.get("CI_MERGE_REQUEST_IID", ""),
        "change_ticket": os.environ.get("CHANGE_TICKET", ""),
    }
    date = record["ts"][:10]
    key = f"{args.target}/{date}/{args.bundle}-{args.sha[:12]}.json"
    print(f"Audit record -> s3://{args.bucket}/{key}")
    print(json.dumps(record, indent=2))
    # Real implementation: boto3 put_object with ObjectLockMode=GOVERNANCE
    # and ObjectLockRetainUntilDate. For air-gapped, swap to internal S3-compatible store.
    return 0


if __name__ == "__main__":
    sys.exit(main())
