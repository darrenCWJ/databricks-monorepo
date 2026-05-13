# Compliance — cdo-platform

This directory holds the operational documentation for the four compliance
postures we maintain:

- `pdpa.md` — Singapore PDPA (data residency + right to erasure)
- `pii.md` — column-level PII handling
- `soc2.md` — change control, audit trail, access reviews
- `regulated-workspace.md` — private connectivity, optional internal mirror,
  hardening that approximates FedRAMP-style controls for Singapore deployment

Each document maps controls to repository artefacts (which files, which CI
checks, which Databricks resources implement the control).
