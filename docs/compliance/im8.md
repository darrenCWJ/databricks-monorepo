# IM8 controls (Singapore Government Instruction Manual 8)

This document maps the IM8 controls we implement for the CDO data platform.

## Scope

- **Maximum classification handled:** Restricted (per platform-team decision)
- **Operating tier:** Tier 1 (internal mirror mandatory; SGNet for users; pinned SHAs everywhere; annual penetration test)
- **Hosting:** AWS GCC tenants — `gcc-aws-dev`, `gcc-aws-staging`, `gcc-aws-prod`
- **Region:** `ap-southeast-1`
- **ICA status:** Out of scope under waiver/exception (see §6 below)

> Caveat: IM8 evolves. Check this document against your agency's current ISO
> (Information Security Officer) guidance every release cycle.

## 1. Data classification

Every column in every dbt model and bundle schema declares:

| Field | Allowed values |
|---|---|
| `meta.classification` | `Official-Open` / `Official-Closed` / `Restricted` / `Confidential` |
| `meta.sensitivity` | `Sensitive-Normal` / `Sensitive-High` / `NA` |
| `meta.retention_days` | positive integer per IM8 / PDPA retention schedule |

The pre-commit hook `tools/scripts/check_pii_contract.py` enforces presence
and validates the vocabulary. MRs that introduce a column tagged
`Restricted` are auto-routed to `@cdo/restricted-cleared` for approval
(CODEOWNERS rule).

Unity Catalog tags propagate classification at dbt run time so masking and
access controls can act on them.

## 2. Hosting on GCC

- All three Databricks workspaces are deployed inside agency-procured GCC AWS
  tenants. `databricks.yml` references them as `dev-cdo.gcc.databricks.com`
  etc — replace with the exact endpoints your ICAO provides.
- Cluster images use the Databricks Runtime version approved on the
  GCC tenant baseline (currently `15.4.x-scala2.12`).
- All S3 buckets created in the GCC account, encrypted with KMS CMKs whose
  key policy is scoped to GCC IAM roles only.
- No cross-account access to non-GCC AWS accounts.

## 3. Network — SGNet + PrivateLink

- Databricks workspaces deployed with PrivateLink — no public endpoint.
- Engineer access only via SGNet VPN to the agency network, then to the GCC
  VPC via VPN/peering.
- NAT egress restricted to allow-list:
  - Databricks control plane (GCC region endpoints)
  - GitLab.com (or internal GitLab if used)
  - Internal Artifactory (`artifactory.cdo.gov.sg`) — see §4
  - AWS service endpoints (S3, Secrets Manager, KMS, CloudWatch)
- Cluster bootstrap probe (`tools/scripts/probe_egress.py`, TODO) confirms no
  unintended internet egress.

## 4. Supply chain (Tier 1 mandatory at Restricted)

- Internal Artifactory PyPI mirror is the **default** index in
  `pyproject.toml`. Public PyPI is blocked at the network layer.
- Internal Maven/Ivy mirror for sbt: configure in `~/.sbt/repositories`.
- All `.pre-commit-config.yaml` revs move to SHA pinning (TODO).
- CI image (`python:3.11-slim`) replaced by an internally-mirrored
  derivative; pinned by digest.
- `pip-audit` runs in CI against the internal CVE feed; CI fails on Critical
  findings.

## 5. ICTSS — security baseline

| Control | Implementation |
|---|---|
| MFA | Mandatory on Databricks, GitLab, AWS (SAML federation from agency IdP) |
| Encryption at rest | KMS CMK on every S3 bucket; Delta tables inherit |
| Encryption in transit | TLS 1.2+ enforced; Databricks REST traffic over PrivateLink |
| Vuln management | Daily `pip-audit` + Trivy scan; Critical CVEs fixed within 7 days |
| Patch cadence | Databricks Runtime version bumped each LTS release |
| Logging | Audit log writer (S3 + Object Lock) — SIEM forwarder is a TODO |
| MFA on service accounts | OAuth M2M for SP; tokens rotated automatically |
| Access reviews | Quarterly per `docs/runbooks/quarterly-access-review.md` |

## 6. ICA waiver

The platform is operating under an ICA waiver / exception (per
agency decision). Implications captured here:

- No formal SRA / penetration test artefacts are produced.
- A residual-risk log is still maintained at `docs/compliance/residual-risk.md` (TODO)
  for internal traceability.
- If the waiver is revoked, the platform must produce SRA + PT + Residual Risk
  Register before the next release.

## 7. Personnel

- `@cdo/restricted-cleared` GitLab group lists individuals cleared to access
  Restricted data. Membership is gated by HR.
- CODEOWNERS routes any MR touching `meta.classification: Restricted` to
  this group. Author cannot approve.
- Agents (AI coding assistants) are non-persons; they can propose MRs but
  cannot be members of cleared groups. Human review is always required.

## 8. DLP

- `tools/scripts/dlp_check.py` (TODO) scans export jobs for Restricted-tagged
  columns and either blocks the export or applies redaction.
- CSV / JSON exports prepended with a classification header line.

## 9. Mapping to repo artefacts (cheat-sheet)

| IM8 area | File(s) |
|---|---|
| Classification contract | `dbt/*/schema.yml`, `tools/scripts/check_pii_contract.py` |
| GCC hosting | `databricks.yml`, `infra/terraform-databricks/main.tf` |
| Internal index | `pyproject.toml` `[[tool.uv.index]]` |
| SGNet/PrivateLink | infra-side (out of repo); documented here |
| Audit logging | `tools/scripts/audit_log.py` |
| Access review | `tools/scripts/dump_access.py` + `docs/runbooks/quarterly-access-review.md` |
| Personnel routing | `CODEOWNERS` (`@cdo/restricted-cleared`) |
| DLP | `tools/scripts/dlp_check.py` (TODO) |
| ICA | waivered — see §6 |
