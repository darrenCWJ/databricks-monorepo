#!/usr/bin/env python3
"""Import an existing Databricks Job into a target app directory.

Usage:
    uv run python tools/scripts/import_job.py <job_id> <target_app_dir>

Example:
    uv run python tools/scripts/import_job.py 987654321 apps/finance-payment-recon

What it does:
1. Calls `databricks bundle generate job --existing-job-id <id>` to dump the
   job's resources/jobs/<name>.yml.
2. Walks the YAML and rewrites:
   - hardcoded catalog names -> ${var.catalog}
   - workspace notebook paths -> ./notebooks/<file>
   - hardcoded cluster_node_type_id / num_workers -> ${var.cluster_*}
   - removes workspace-managed fields (job_id, creator_user_name, ...).
3. Pulls referenced notebooks from the workspace into ./notebooks/.
4. Writes IMPORT_REPORT.md flagging items that need human review.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

WORKSPACE_FIELDS_TO_STRIP = (
    "job_id",
    "creator_user_name",
    "created_time",
    "run_as_user_name",
)


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def export_raw_job(job_id: str, target: Path) -> dict:
    """Dump the raw job JSON for the IMPORT_REPORT reference."""
    p = run(["databricks", "jobs", "get", "--job-id", job_id])
    raw = json.loads(p.stdout)
    (target / ".import").mkdir(parents=True, exist_ok=True)
    (target / ".import" / "raw-job.json").write_text(json.dumps(raw, indent=2))
    return raw


def generate_bundle(job_id: str, target: Path) -> Path:
    """Use `databricks bundle generate job` to produce starter YAML."""
    resources = target / "resources" / "jobs"
    resources.mkdir(parents=True, exist_ok=True)
    sources = target
    run([
        "databricks", "bundle", "generate", "job",
        "--existing-job-id", job_id,
        "--config-dir", str(resources),
        "--source-dir", str(sources),
    ])
    # Find the YAML file the CLI emitted (named after the job).
    yamls = list(resources.glob("*.yml")) + list(resources.glob("*.yaml"))
    if not yamls:
        raise SystemExit(f"No bundle YAML produced under {resources}")
    return yamls[-1]


def rewrite_yaml(yml_path: Path, flags: list[str]) -> None:
    """Apply substitutions to make the imported YAML repo-native."""
    text = yml_path.read_text()

    # 1. Strip workspace-managed scalar fields.
    for field in WORKSPACE_FIELDS_TO_STRIP:
        text = re.sub(rf"^\s*{field}:.*$\n?", "", text, flags=re.MULTILINE)

    # 2. Parameterise catalog references.
    catalog_pattern = re.compile(r"(catalog:\s*)(cdo_(?:dev|staging|prod))", re.IGNORECASE)
    if catalog_pattern.search(text):
        text = catalog_pattern.sub(r"\1${var.catalog}", text)
        flags.append("catalog: hardcoded values parameterised to ${var.catalog}")

    # 3. Convert workspace notebook paths to local ./notebooks/...
    nb_pattern = re.compile(r"notebook_path:\s*(/Workspace/[^\s]+)")
    notebooks_to_pull: list[str] = []
    def nb_replace(m: re.Match) -> str:
        ws_path = m.group(1)
        local_name = Path(ws_path).name
        if not local_name.endswith((".py", ".ipynb", ".sql", ".r", ".scala")):
            local_name += ".py"
        notebooks_to_pull.append(ws_path)
        return f"notebook_path: ./notebooks/{local_name}"
    text = nb_pattern.sub(nb_replace, text)
    if notebooks_to_pull:
        flags.append(
            f"Notebook paths rewritten to local ./notebooks/. Pull required for: "
            + ", ".join(notebooks_to_pull)
        )

    # 4. Parameterise node_type_id and num_workers in inline clusters.
    if re.search(r"node_type_id:\s*\w+", text):
        text = re.sub(r"(node_type_id:\s*)(\S+)", r"\1${var.cluster_node_type_id}", text)
        flags.append("node_type_id parameterised to ${var.cluster_node_type_id}")
    if re.search(r"num_workers:\s*\d+", text):
        text = re.sub(r"(num_workers:\s*)(\d+)", r"\1${var.cluster_num_workers}", text)
        flags.append("num_workers parameterised to ${var.cluster_num_workers}")

    # 5. Add a stub run_as block reminder.
    if "run_as:" not in text:
        flags.append(
            "No run_as: block detected. Add run_as: { service_principal_name: ${var.staging_sp} } "
            "before deploying to staging/prod."
        )

    # 6. Note hardcoded paths (s3://, dbfs:/, abfss://).
    for scheme in ("dbfs:/", "s3://", "abfss://", "/Workspace/Users/"):
        if scheme in text:
            flags.append(
                f"Hardcoded path containing `{scheme}` found. Consider replacing with "
                f"Unity Catalog volume path or ${{var.catalog}}-relative reference."
            )

    yml_path.write_text(text)


def pull_notebooks(raw_job: dict, target: Path, flags: list[str]) -> None:
    """Find every workspace notebook the job references and copy it into ./notebooks/.
    """
    nb_dir = target / "notebooks"
    nb_dir.mkdir(parents=True, exist_ok=True)
    paths: set[str] = set()
    for task in (raw_job.get("settings", {}).get("tasks") or []):
        nb = task.get("notebook_task", {}).get("notebook_path")
        if nb and nb.startswith("/Workspace/"):
            paths.add(nb)
    for ws_path in paths:
        local_name = Path(ws_path).name
        if not local_name.endswith((".py", ".ipynb", ".sql", ".r", ".scala")):
            local_name += ".py"
        local = nb_dir / local_name
        try:
            run([
                "databricks", "workspace", "export",
                "--format", "SOURCE",
                ws_path, str(local),
            ])
        except subprocess.CalledProcessError as e:
            flags.append(
                f"Could not auto-pull notebook {ws_path}: {e.stderr.strip()}. "
                f"Pull manually with `databricks workspace export {ws_path} {local}`."
            )


def write_report(target: Path, job_id: str, flags: list[str]) -> None:
    report = target / "IMPORT_REPORT.md"
    body = [
        f"# Import report — Databricks Job {job_id}",
        "",
        "Generated by `tools/scripts/import_job.py`. Resolve every item below "
        "before opening the MR.",
        "",
        "## Items needing human review",
        "",
    ]
    if flags:
        for f in flags:
            body.append(f"- [ ] {f}")
    else:
        body.append("- (none flagged — review the bundle.yml manually anyway)")
    body += [
        "",
        "## Manual checklist (always required)",
        "- [ ] Logic moved from notebook into `src/`",
        "- [ ] At least one unit test added",
        "- [ ] `just lint` and `just test` pass",
        "- [ ] `just bundle-validate` passes",
        "- [ ] `run_as:` set for staging and prod targets",
        "- [ ] `bundle.yml` reviewed for residual hardcoded values",
        "- [ ] Tracking row added to `docs/migrations/INDEX.md`",
        "",
        "When all boxes are ticked, delete this file in the MR that does cut-over "
        "(Step 10 in the runbook).",
    ]
    report.write_text("\n".join(body) + "\n")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("job_id")
    p.add_argument("target", help="Target app directory, e.g. apps/finance-payment-recon")
    args = p.parse_args()

    target = Path(args.target).resolve()
    if not target.exists():
        raise SystemExit(f"Target {target} does not exist — run `just new-app ...` first.")

    flags: list[str] = []
    print(f"[1/4] Exporting raw job {args.job_id}...")
    raw = export_raw_job(args.job_id, target)
    print(f"[2/4] Generating bundle yaml...")
    yml = generate_bundle(args.job_id, target)
    print(f"      Wrote {yml.relative_to(target.parent.parent)}")
    print(f"[3/4] Rewriting bundle.yml for repo conventions...")
    rewrite_yaml(yml, flags)
    print(f"      Applied {len(flags)} substitutions")
    print(f"[4/4] Pulling notebooks from workspace...")
    pull_notebooks(raw, target, flags)
    write_report(target, args.job_id, flags)
    print(f"\nDone. Review {target.relative_to(target.parent.parent)}/IMPORT_REPORT.md "
          f"and resolve each item before opening an MR.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
