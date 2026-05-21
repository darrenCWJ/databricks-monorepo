## What
<!-- One paragraph: what does this MR do? -->

## Why
<!-- Link to issue / change ticket. REQUIRED for SOC2 audit trail. -->
- Change ticket: CHG-XXXXX
- Related issue: #

## How tested
- [ ] Ran `make test P=<scope>` locally
- [ ] Added/updated unit tests
- [ ] `make bundle-validate P=<bundle>` passes
- [ ] Verified in dev workspace (paste link or screenshot)

## Risk & rollback
<!-- What breaks if this is wrong? How do we roll back? -->

## Data classification
<!-- Tick all that apply -->
- [ ] Touches PII columns
- [ ] Changes data residency (must remain in Singapore)
- [ ] Adds/removes Unity Catalog grants
- [ ] None of the above

## Compliance
- [ ] CODEOWNERS approver (NOT the author) has reviewed
- [ ] No secrets in this MR (`detect-private-key` pre-commit passed)
