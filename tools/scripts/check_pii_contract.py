#!/usr/bin/env python3
"""IM8 + PDPA + ACL contract checker.

Every column in schema.yml must declare:
- meta.pii             true | false
- meta.classification  Official-Open | Official-Closed | Restricted | Confidential
- meta.sensitivity     Sensitive-Normal | Sensitive-High | NA
- meta.retention_days  positive integer

Restricted (or Confidential) columns must ALSO declare:
- meta.mask_function   the UC function applied to mask non-cleared callers
  (or meta.no_mask_required: true with a justification reviewed by governance)

Tables containing any Restricted PK or join key SHOULD declare a row filter
in config.row_filter (warned, not blocked — opt-in for sensitive aggregates).
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

VALID_CLASS = {"Official-Open", "Official-Closed", "Restricted", "Confidential"}
VALID_SENS = {"Sensitive-Normal", "Sensitive-High", "NA"}
NEEDS_MASK = {"Restricted", "Confidential"}


def check_file(path: Path) -> tuple[list[str], list[str]]:
    errs: list[str] = []
    warns: list[str] = []
    try:
        doc = yaml.safe_load(path.read_text())
    except Exception as e:
        return [f"{path}: cannot parse yaml: {e}"], warns
    if not isinstance(doc, dict):
        return errs, warns
    for model in doc.get("models", []) or []:
        model_name = model.get("name", "<unnamed>")
        has_restricted_col = False
        has_row_filter = bool((model.get("config") or {}).get("row_filter"))
        for col in model.get("columns", []) or []:
            meta = col.get("meta") or {}
            col_name = col.get("name", "<unnamed>")
            tag = f"{path}: model `{model_name}` column `{col_name}`"
            if "pii" not in meta:
                errs.append(f"{tag} missing meta.pii (must be true|false)")
            classification = meta.get("classification")
            if classification is None:
                errs.append(f"{tag} missing meta.classification (IM8)")
            elif classification not in VALID_CLASS:
                errs.append(
                    f"{tag} invalid classification `{classification}` — "
                    f"must be one of {sorted(VALID_CLASS)}"
                )
            if "sensitivity" not in meta:
                errs.append(f"{tag} missing meta.sensitivity (IM8)")
            elif meta["sensitivity"] not in VALID_SENS:
                errs.append(
                    f"{tag} invalid sensitivity `{meta['sensitivity']}` — "
                    f"must be one of {sorted(VALID_SENS)}"
                )
            if "retention_days" not in meta:
                errs.append(f"{tag} missing meta.retention_days (PDPA + IM8 schedule)")
            elif not isinstance(meta["retention_days"], int) or meta["retention_days"] <= 0:
                errs.append(f"{tag} retention_days must be a positive integer")
            # ACL: Restricted+ columns need a mask
            if classification in NEEDS_MASK:
                has_restricted_col = True
                if "mask_function" not in meta and not meta.get("no_mask_required"):
                    errs.append(
                        f"{tag} classified `{classification}` — must declare "
                        f"meta.mask_function (or meta.no_mask_required: true "
                        f"with governance-approved justification)"
                    )
        # ACL: warn if Restricted columns and no row filter
        if has_restricted_col and not has_row_filter:
            warns.append(
                f"{path}: model `{model_name}` has Restricted columns but no "
                f"config.row_filter. Consider declaring one (governance review)."
            )
    return errs, warns


def main(argv: list[str]) -> int:
    all_errs: list[str] = []
    all_warns: list[str] = []
    for a in argv:
        errs, warns = check_file(Path(a))
        all_errs.extend(errs)
        all_warns.extend(warns)
    if all_warns:
        print("WARNINGS:", file=sys.stderr)
        for w in all_warns:
            print(f"  - {w}", file=sys.stderr)
    if all_errs:
        print("ERRORS:", file=sys.stderr)
        for e in all_errs:
            print(f"  - {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
