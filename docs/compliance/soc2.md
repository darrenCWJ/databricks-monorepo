# SOC 2 — Type II control mapping

> How the monorepo evidences SOC 2 Trust Services Criteria.

## Scope

Type II = "controls operate effectively over a period of time" (typically
12 months). The auditor verifies that our controls are:

1. Documented (this folder + `runbooks/`).
2. Implemented (the platform actually behaves as described).
3. Operating consistently (evidence over the audit window).

## TSC mapping

| Criterion | What it requires | How we evidence it |
|---|---|---|
| **CC1 — Control environment** | Documented governance, codes of conduct, training. | This monorepo + `docs/` + HR training records. |
| **CC2 — Communication** | Internal + external comms about responsibilities. | `AGENTS.md` per project + CODEOWNERS routing + `#data-platform` Slack channel. |
| **CC3 — Risk assessment** | Documented risk register, reviewed quarterly. | `docs/risk-register.md` (TODO) + ADRs for material decisions. |
| **CC4 — Monitoring** | Active monitoring of controls. | `tools/scripts/audit_log.py` + `system.audit.*` system tables + Databricks SQL alerts. |
| **CC5 — Control activities** | Logical controls operating as designed. | This whole repo. |
| **CC6 — Logical access** | Access provisioning + revocation. | `runbooks/access-control.md`, `runbooks/cleared-group-intake.md`. Terraform-managed grants. |
| **CC7 — System operations** | Vulnerability mgmt, patching, incident response. | CI security stage, pre-commit hooks, PagerDuty rotation. |
| **CC8 — Change management** | Authorised changes only, segregation of duties. | MR template + CODEOWNERS + distinct-approver rule on prod deploys. |
| **CC9 — Risk mitigation** | Specific to data confidentiality + integrity. | Column masks (`libs/common-masks/`) + WORM audit logs. |

## Three controls auditors care about most

### 1. Segregation of duties on prod deploy

The CI pipeline enforces: the person who merged the last MR to a release
branch CANNOT click "Play" on `deploy-prod`. Evidence:

- GitLab API: pipeline triggered_by → must differ from merge commit
  author.
- `system.audit.deploy_events`: every deploy carries `deployer_user_id`
  and the corresponding merge_user_id.

Test the auditor runs: pull a sample of 20 prod deploys over the audit
window; verify all 20 have distinct values.

### 2. Every change has a change ticket

The MR template requires `PROJ-XXXX`. Pre-merge CI checks the field is
non-empty and links to a real Jira ticket. Evidence:

- GitLab MR list with `change_ticket_id` field populated.
- `system.audit.merge_events` cross-referenced with Jira API.

### 3. Audit log is WORM

Every deploy and access event writes to `s3://cdo-soc2-audit/` with
object lock + retention period set to 7 years. Bucket policy denies
DELETE except via a break-glass procedure.

## Evidence collection

Quarterly, platform team runs:

```bash
python tools/scripts/soc2_evidence_pack.py --quarter Q1 --year 2026
```

Output: zip with:
- All MRs merged that quarter.
- All deploys per environment that quarter.
- All access grants applied + revoked that quarter.
- Sample of CODEOWNERS approvals.
- Sample of column-mask test runs.

Pack is handed to the auditor for sampling.

## What's NOT in scope

- Vendor management (third-party SaaS reviews).
- Physical security (AWS GCC scope).
- Business continuity (DR drills are run by IT separately).
