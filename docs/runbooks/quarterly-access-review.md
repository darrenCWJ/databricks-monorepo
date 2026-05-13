# Quarterly access review

## Cadence
First Monday of January, April, July, October.

## Who runs it
@cdo/data-governance with @cdo/security observing.

## Steps

1. Run dump:
   ```bash
   just dump-access prod
   ```
   Outputs `reviews/YYYY-MM-DD/codeowners.csv`, `databricks-acls.csv`, `uc-grants.csv`.
2. For each row in `codeowners.csv`, confirm the listed group still owns that path.
3. For each Databricks ACL, confirm the user/group has a current business need.
4. For each UC grant on `pii: true` columns or `audit` schemas, re-attest.
5. File findings as MRs that remove stale entries.
6. Archive the `reviews/` folder for the quarter — commit it to the repo as
   audit evidence (the folder is intentionally not gitignored).
