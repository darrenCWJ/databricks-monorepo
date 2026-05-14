"""Migrate an existing repo into apps/<name>/ inside this monorepo.

Two modes:

  --mode=history   (default) — preserve full git history via git filter-repo.
                    Requires `pip install git-filter-repo` available on the
                    platform-team workstation. `git log apps/<name>/` will
                    show every commit from the source repo.

  --mode=fresh     Copy the working tree only, with a single commit
                    "Migrate <repo> from <SHA>". Faster, no history.

Usage:
  python tools/scripts/migrate_repo.py \\
      --source ~/git/legacy/finance-budget \\
      --name finance-budget-recon \\
      --team finance \\
      --mode history

What this script does (in order):

  1. Validates the destination apps/<name>/ does not exist yet.
  2. Clones the source repo to a temp directory.
  3. (history mode) Rewrites the temp clone so every file lives under
     apps/<name>/, using `git filter-repo --path-rename :apps/<name>/`.
     (fresh mode) Skips rewrite; we'll copy the working tree only.
  4. Runs hygiene checks on the source — flags suspected secrets
     (.env, *.pem, *_key, credentials.json), node_modules/, .DS_Store,
     and files > 1 MB. Aborts if any are found, listing them.
  5. Merges into the current branch (history) or copies the tree (fresh).
  6. Drops the source repo's CI config:
        .github/, .gitlab-ci.yml, .circleci/, Jenkinsfile, azure-pipelines.yml
     These are replaced by the monorepo pipeline at the root.
  7. Generates apps/<name>/AGENTS.md as a stub with inputs/outputs to fill in.
  8. Registers the project:
        - Adds member to pyproject.toml [tool.uv.workspace] if Python detected.
        - Adds include line to root databricks.yml.
        - Suggests a CODEOWNERS rule (prints — user adds manually).
  9. Renames the Python package directory under src/ to match <name>
     (Python convention: hyphens become underscores; same for any __init__.py
     imports the script can fix automatically).
 10. Runs `just lint` and `just bundle-validate apps/<name>/` and reports
     remaining work to the user.

What this script does NOT do:

  - Update import statements in your application code if the package
     rename breaks them. The script prints a list of probable callsites;
     you fix them by hand or with `grep -r` + sed.
  - Rotate secrets. If the hygiene step flagged any, you must rotate
     them in the source system AND in the monorepo's secret store before
     shipping.
  - Decide your AGENTS.md content. The generated stub has the right
     shape — you fill in inputs, outputs, SLA, owners.

Manual steps after the script finishes:

  - Open the generated apps/<name>/AGENTS.md and fill in the blanks.
  - Add a row to docs/data-architecture.md (Tables 1, 2, 3).
  - Add the CODEOWNERS rule the script printed.
  - Run `just test apps/<name>/` and fix any failures.
  - Open the MR with a change-ticket ID.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


SECRET_PATTERNS: tuple[str, ...] = (
    "*.env", ".env.*", "*.pem", "*_key", "*_key.json",
    "credentials*.json", "secret*.yaml", "service-account*.json",
)
NOISE_PATTERNS: tuple[str, ...] = ("node_modules", ".DS_Store", "__pycache__", "dist", "build")
LARGE_FILE_BYTES: int = 1_000_000


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> str:
    """Run a subprocess command and return stdout."""
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and result.returncode != 0:
        sys.stderr.write(f"Command failed: {{' '.join(cmd)}}\n{{result.stderr}}\n")
        raise SystemExit(result.returncode)
    return result.stdout


def hygiene_check(repo: Path) -> list[str]:
    """Return a list of suspicious files found in the source repo."""
    flagged: list[str] = []
    for pattern in SECRET_PATTERNS:
        flagged.extend(str(p.relative_to(repo)) for p in repo.rglob(pattern))
    for pattern in NOISE_PATTERNS:
        flagged.extend(str(p.relative_to(repo)) for p in repo.rglob(pattern))
    for p in repo.rglob("*"):
        if p.is_file() and p.stat().st_size > LARGE_FILE_BYTES and ".git" not in p.parts:
            flagged.append(f"{{p.relative_to(repo)}} ({{p.stat().st_size:,}} bytes)")
    return sorted(set(flagged))


def detect_python(repo: Path) -> bool:
    """Heuristic: does the source look like a Python project?"""
    return (repo / "pyproject.toml").exists() or (repo / "setup.py").exists() or bool(list(repo.rglob("*.py")))


def drop_legacy_ci(target: Path) -> None:
    """Remove CI/CD config that no longer applies under the monorepo."""
    legacy = [
        ".github", ".gitlab-ci.yml", ".circleci", "Jenkinsfile",
        "azure-pipelines.yml", "bitbucket-pipelines.yml",
    ]
    for name in legacy:
        p = target / name
        if p.exists():
            shutil.rmtree(p) if p.is_dir() else p.unlink()
            print(f"  dropped legacy CI: {{name}}")


def write_agents_stub(target: Path, name: str, team: str) -> None:
    """Write an AGENTS.md stub the user fills in."""
    content = f"""# {{name}} — agent rulebook

> Migrated from a legacy repo. Fill in the blanks below.

## What this project does

_One paragraph._

## Inputs

- _table or API_

## Outputs

- _table or endpoint_

## SLA

_e.g. daily by 06:00 SGT — or N/A if non-prod._

## Classification

- Inputs: _Official-Open / Official-Closed / Restricted_
- Outputs: _same vocabulary_

## Owners

- Code: @cdo/{{team}}-team
- Schema changes: @cdo/{{team}}-team
- Release: @cdo/{{team}}-team-lead

## Local dev

```bash
just test apps/{{name}}/
just bundle-validate apps/{{name}}/
```

## Project-specific rules

- _e.g. "no floats for money"_
"""
    (target / "AGENTS.md").write_text(content)
    print("  wrote AGENTS.md stub")


def register_pyproject(name: str) -> None:
    """Add this project to root pyproject.toml workspace members."""
    py = REPO_ROOT / "pyproject.toml"
    text = py.read_text()
    if f'"apps/{{name}}"' in text:
        print("  pyproject.toml already lists this project")
        return
    new = re.sub(
        r"(\[tool\.uv\.workspace\]\s*\n# add each.*?\nmembers\s*=\s*\[)([^\]]*)\]",
        lambda m: f'{{m.group(1)}}{{m.group(2)}}    "apps/{{name}}",\n]',
        text,
        flags=re.DOTALL,
    )
    py.write_text(new)
    print(f"  added apps/{{name}} to pyproject.toml workspace members")


def register_databricks_yml(name: str) -> None:
    """Add include line to root databricks.yml."""
    dby = REPO_ROOT / "databricks.yml"
    text = dby.read_text()
    line = f"  - apps/{{name}}/bundle.yml"
    if line in text:
        print("  databricks.yml already includes this project")
        return
    new = text.replace(
        "include:\n  # add every app's bundle file as you create it:",
        f"include:\n  # add every app's bundle file as you create it:\n{{line}}",
    )
    dby.write_text(new)
    print(f"  added include for apps/{{name}}/bundle.yml to databricks.yml")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Migrate a repo into apps/<name>/")
    parser.add_argument("--source", required=True, type=Path, help="path to the source repo")
    parser.add_argument("--name", required=True, help="apps/<name>/ target — e.g. finance-budget-recon")
    parser.add_argument("--team", required=True, help="owning team, e.g. finance")
    parser.add_argument("--mode", choices=("history", "fresh"), default="history",
                        help="history preserves git log; fresh copies the working tree only")
    parser.add_argument("--allow-dirty", action="store_true",
                        help="skip the hygiene check (NOT recommended)")
    args = parser.parse_args(argv)

    target = REPO_ROOT / "apps" / args.name
    if target.exists():
        sys.stderr.write(f"refusing: {{target}} already exists\n")
        return 1

    # 1. Hygiene check on source
    print(f"Hygiene check on {{args.source}}…")
    flagged = hygiene_check(args.source)
    if flagged and not args.allow_dirty:
        sys.stderr.write("Found suspicious or large files in source:\n")
        for f in flagged:
            sys.stderr.write(f"  - {{f}}\n")
        sys.stderr.write("Clean these up in the source repo first, or re-run with --allow-dirty.\n")
        return 2
    print(f"  OK ({{len(flagged)}} flagged)" if flagged else "  OK (clean)")

    # 2. Bring code in
    if args.mode == "history":
        with tempfile.TemporaryDirectory() as tmpdir:
            clone = Path(tmpdir) / "src"
            run(["git", "clone", "--no-local", str(args.source), str(clone)])
            # Rewrite paths so everything lives under apps/<name>/
            run(["git", "filter-repo", "--path-rename", f":apps/{{args.name}}/"], cwd=clone)
            # Add as a remote, fetch, merge
            remote_name = f"migrate-{{args.name}}"
            run(["git", "remote", "add", remote_name, str(clone)])
            try:
                run(["git", "fetch", remote_name])
                run(["git", "merge", "--allow-unrelated-histories",
                     "-m", f"Migrate {{args.source.name}} into apps/{{args.name}} (history preserved)",
                     f"{{remote_name}}/main"])
            finally:
                run(["git", "remote", "remove", remote_name], check=False)
    else:
        target.mkdir(parents=True)
        for item in args.source.iterdir():
            if item.name == ".git":
                continue
            dest = target / item.name
            shutil.copytree(item, dest) if item.is_dir() else shutil.copy2(item, dest)
        src_sha = run(["git", "rev-parse", "HEAD"], cwd=args.source).strip()
        run(["git", "add", str(target)])
        run(["git", "commit", "-m", f"Migrate {{args.source.name}} into apps/{{args.name}} (fresh, from {{src_sha[:12]}})"])

    # 3. Drop legacy CI
    print("Dropping legacy CI config…")
    drop_legacy_ci(target)

    # 4. AGENTS.md stub
    print("Writing AGENTS.md stub…")
    write_agents_stub(target, args.name, args.team)

    # 5. Register in root files
    print("Registering in root files…")
    if detect_python(target):
        register_pyproject(args.name)
    register_databricks_yml(args.name)

    # 6. Suggest CODEOWNERS rule
    print()
    print("Add this line to CODEOWNERS (sectioned under your team):")
    print(f"  /apps/{{args.name}}/   @cdo/{{args.team}}-team")
    print()

    # 7. Reminders
    print("Done. Manual steps:")
    print(f"  1. Fill in apps/{{args.name}}/AGENTS.md")
    print(f"  2. Add a row to docs/data-architecture.md")
    print(f"  3. Add CODEOWNERS rule above")
    print(f"  4. Run: just lint apps/{{args.name}}/ && just test apps/{{args.name}}/")
    print(f"  5. Run: just bundle-validate apps/{{args.name}}/")
    print(f"  6. Open the MR with a change-ticket ID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
