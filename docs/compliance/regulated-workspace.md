# Regulated-workspace hardening (IM8-aligned)

We operate at **Tier 1** because the platform handles data up to IM8
Restricted classification.

## Tier ladder mapped to classification

| Highest classification | Tier | What's mandatory |
|---|---|---|
| Official (Open) | 0 | Standard hardening; allow-listed egress; external PyPI OK |
| Official (Closed) | 0 | + data inventory tagged |
| **Restricted (current)** | **1** | Internal Artifactory mandatory; SHA-pinned deps; SGNet for users; annual PT; daily vuln scan |
| Confidential | 2 | Air-gapped CI; no internet egress; SBOM; 6-monthly PT; FIPS crypto |
| Secret | (out of scope) | Agency-dedicated isolated stack |

## What Tier 1 means in this repo

- `pyproject.toml` `[[tool.uv.index]]` points at internal Artifactory **by default** (not commented).
- `.pre-commit-config.yaml` revs migrated to SHA pinning (TODO; v1 of this scaffold still uses version pins).
- `.gitlab-ci.yml` adds `pip-audit` and `trivy` gates on every build.
- Databricks workspaces sit behind PrivateLink on the GCC tenant; engineers reach them via SGNet VPN.
- No public endpoints; cluster bootstrap probe verifies egress restrictions.

## Network

- PrivateLink + VPC peering (GCC standard).
- NAT egress allow-list (Databricks control plane, internal Artifactory, AWS service endpoints, GitLab.com).
- Cluster bootstrap test fails if `8.8.8.8` reachable.

## Secrets

- No secrets in repo. `detect-private-key` pre-commit enforces.
- Databricks secret scopes back to AWS Secrets Manager (GCC region).
- GitLab CI/CD variables scoped to protected branches only.
- Service principals via OAuth M2M; tokens rotated automatically.

## Logging

- Audit log writer writes WORM S3 (current default).
- SIEM forwarder: TODO — flag when destination decided.
- Retention: 7 years (system access logs), 2 years (data access lineage).

## Tier upgrade path

Moving from Tier 1 → Tier 2 (only relevant if classification scope expands
to Confidential):

1. Switch CI runners to internal-only network egress.
2. Generate SBOM at every build; archive to audit bucket.
3. Pen-test cadence to every 6 months.
4. FIPS-validated crypto modules on clusters (DBR FIPS-enabled image).
5. All third-party libraries reviewed by Security before mirror admission.
