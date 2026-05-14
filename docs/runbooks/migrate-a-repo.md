# Runbook: migrate a repo into apps/

Pulls a legacy repository into `apps/<name>/`. Use this whenever you're
adopting an existing pipeline or service into the monorepo for the first
time.

For a brand-new project (no legacy code), see `create-a-new-project.md`
instead.

## Pick a mode

| Mode | When | Trade-off |
|---|---|---|
| `history` (default) | Active repo with commit history you want to keep — blame, release notes, audit trail. | Requires `git filter-repo` installed. Larger initial merge. |
| `fresh` | Dead / abandoned legacy where the working tree is the only thing that matters. | Single "migrated from <SHA>" commit. Faster. History lives in the old repo only. |

If unsure, pick `history` — you can always squash later, you can't recover what you never imported.

## Prerequisites

- You have a local clone of this monorepo on `main`, clean working tree.
- For `history` mode: `pip install git-filter-repo`.
- Source repo is checked out somewhere locally with the commit you want
  to migrate from on `HEAD` of its default branch.
- The source repo has no secrets, no `node_modules/`, no large binaries.
  (The script will check. If it finds any, you clean them up in the
  source first.)

## Steps

1. **Decide the destination name.** Use the standard pattern:
   `apps/<team>-<verb>-<noun>` — e.g. `apps/finance-budget-recon`.

2. **Run the migration script.**

   ```bash
   python tools/scripts/migrate_repo.py \\
       --source ~/git/legacy/finance-budget \\
       --name finance-budget-recon \\
       --team finance \\
       --mode history
   ```

   What it does, in order:
   - Hygiene-checks the source (secrets, large files, junk).
   - Brings the code in under `apps/<name>/` (preserving history in
     `history` mode, copying the working tree in `fresh` mode).
   - Drops the source repo's CI config (`.github/`, `.gitlab-ci.yml`,
     `Jenkinsfile`, etc.) — these are replaced by the monorepo pipeline.
   - Writes an `apps/<name>/AGENTS.md` stub.
   - Registers in `pyproject.toml` workspace (if Python) and
     `databricks.yml` includes.
   - Prints the CODEOWNERS rule you need to add manually.

3. **Fill in `apps/<name>/AGENTS.md`.** The stub has the right shape;
   you complete inputs, outputs, SLA, owners, classification.

4. **Add the CODEOWNERS rule** the script printed. Example:

   ```
   /apps/finance-budget-recon/   @cdo/finance-team
   ```

5. **Add a row to `docs/data-architecture.md`** in Tables 1, 2, and 3.

6. **Convert the bundle config.** If the source repo had a Databricks
   Asset Bundle, edit `apps/<name>/bundle.yml` so:
   - Targets use this repo's environment names (`dev`, `staging`, `prod`).
   - `run_as:` points at our service principal for non-dev targets.
   - Variables reference the platform-team defaults.

   If the source had no DAB, copy the structure from another app's
   `bundle.yml` and adapt.

7. **Run the gates locally:**

   ```bash
   just lint apps/<name>/
   just test apps/<name>/
   just bundle-validate apps/<name>/
   ```

   Expect failures the first time — that's normal. Fix and re-run.

8. **Open the MR.** Use the change-ticket template; flag risk =
   "migration", and mention that a different approver will be needed
   for prod promotion (SOC2).

## What the script does NOT do automatically

- **Update import statements** after the Python package rename.
  The script renames `src/<old_name>/` → `src/<new_name>/`. If your
  application code imports `from <old_name> import foo`, those imports
  break. The script prints a list of probable callsites; fix with
  `grep -r` + sed or by hand.

- **Rotate any secrets it found.** If hygiene flagged a `.env` file or
  a checked-in credential, the script aborts. You rotate the secret in
  the source system, then re-run.

- **Decide the AGENTS.md content.** The stub asks you the right
  questions; you answer them.

## Edge cases

- **Source repo has multiple apps inside it.** Run the script once per
  app, each with a different `--name`. Use `--mode fresh` and
  sub-directory copies, since `git filter-repo` migrates the whole repo
  at once.

- **Source has submodules.** Resolve them first — either vendor the
  submodule code into the source, or replace with a regular Python
  dependency in `pyproject.toml`.

- **Source is huge (>500 MB).** History mode will blow up the monorepo.
  Use `fresh` mode and document the source SHA in an ADR so the history
  stays reachable in the legacy archive.

## Checklist

- [ ] Picked `history` or `fresh` mode
- [ ] Source repo hygiene-checked (no secrets, no junk)
- [ ] Ran `migrate_repo.py` — exit code 0
- [ ] Filled in `apps/<name>/AGENTS.md`
- [ ] Added CODEOWNERS rule
- [ ] Added rows to `docs/data-architecture.md`
- [ ] Converted `bundle.yml` for our environments
- [ ] `just lint` / `just test` / `just bundle-validate` all pass
- [ ] MR opened with change ticket
- [ ] (Optional) Wrote an ADR for the migration

## See also

- `create-a-new-project.md` — brand-new projects (no legacy).
- `branching-strategy.md` — how the migration MR flows through main/release.
- `release-process.md` — staging → prod cadence after the migration lands.
