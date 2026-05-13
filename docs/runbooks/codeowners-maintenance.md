# Runbook: maintaining CODEOWNERS

CODEOWNERS is the most-edited governance file in this monorepo. This runbook
covers when to update it, who approves the change, and what other files must
stay in sync.

## When CODEOWNERS changes

| Moment | Who opens the MR | Who approves |
|---|---|---|
| A new team joins the platform | @cdo/platform-team | @cdo/platform-team + the joining team's lead |
| A team adds a new app/lib/dbt-project | The owning team | The owning team |
| Team renames, splits, merges, or leaves | @cdo/platform-team | Both affected team leads + @cdo/platform-team |
| Quarterly access review | @cdo/data-governance | @cdo/platform-team + @cdo/security |

CODEOWNERS is itself owned by @cdo/platform-team. Any change to the file gets
the same gates as platform-wide rules.

## Files that must stay in sync

When CODEOWNERS changes, other files that name teams must also change. The
`tools/scripts/check_ownership_sync.py` pre-commit hook catches mismatches.

| When CODEOWNERS changes... | Also update... |
|---|---|
| Team renamed (@cdo/oldname -> @cdo/newname) | Every `AGENTS.md` that names the team; `infra/unity-catalog/main.tf` group names; `databricks.yml` service-principal references; `docs/compliance/*.md` references |
| New app prefix introduced (e.g. apps/legal-*) | Root `AGENTS.md` folder map; new prefix added to `apps/<prefix>-*` line in CODEOWNERS |
| Cleared-group changes | Every `dbt/**/schema.yml` reviewers re-attest (file content stays valid) |
| New compliance reviewer team | `.gitlab/merge_request_templates/default.md` if it names reviewers |

## Team rename walkthrough (worked example)

Say `@cdo/supplier-team` renames to `@cdo/procurement-team`. The MR landing
this is large by design — renaming a team is a coordinated platform-level
change, not a sneaky one.

Files to edit in one MR:
- `CODEOWNERS` (lines starting `/apps/supplier-*`, `/libs/supplier-common`,
  `/dbt/supplier`, `/docs/runbooks/supplier-*.md`)
- Rename directories: `apps/supplier-*` -> `apps/procurement-*`,
  `libs/supplier-common` -> `libs/procurement-common`,
  `dbt/supplier` -> `dbt/procurement`
- `pyproject.toml` workspace members
- `infra/unity-catalog/main.tf` group resource names
- `databricks.yml` variable defaults (supplier_sp -> procurement_sp)
- `docs/compliance/im8.md`, `pdpa.md`, `soc2.md` (any references)
- Root `AGENTS.md` folder map

After local edits, `just lint` will run `check_ownership_sync.py` and fail
fast if any reference was missed.

## Quarterly access review

First Monday of January / April / July / October:

1. `just dump-access prod` produces three CSVs (CODEOWNERS expansion,
   Databricks ACLs, UC grants).
2. @cdo/data-governance + @cdo/security walk through each row.
3. Stale entries removed via MR.
4. The `reviews/YYYY-MM-DD/` folder is committed as audit evidence
   (intentionally NOT gitignored).

See `docs/runbooks/quarterly-access-review.md` for the full process.

## Who can change what

| File | Owner | Other approvers needed |
|---|---|---|
| CODEOWNERS itself | @cdo/platform-team | The team(s) being added or removed |
| Team's own line in CODEOWNERS | That team | @cdo/platform-team |
| AGENTS.md (root) | @cdo/platform-team | None |
| `apps/<team>-*/AGENTS.md` | The team | None |
| `infra/unity-catalog/main.tf` (group names) | @cdo/platform-team | @cdo/data-governance + @cdo/security |
| `databricks.yml` (SP variable defaults) | @cdo/platform-team | None |
| `.gitlab/merge_request_templates/default.md` | @cdo/platform-team | @cdo/security |
| `docs/compliance/*.md` | @cdo/data-governance + @cdo/security | None |
| `docs/onboarding/*.md` | @cdo/platform-team | None |
| `docs/runbooks/<team>-*.md` | The team | None |
| `dbt/<team>/**/schema.yml` (Restricted columns) | The team | @cdo/data-governance + @cdo/restricted-cleared |

## Verifying sync (locally and in CI)

Before opening the MR:

```bash
uv run python tools/scripts/check_ownership_sync.py
```

This is also wired as a pre-commit hook and as a CI check, so the MR will fail
if it lands out of sync.

