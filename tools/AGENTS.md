# tools/ — agent rules

> Extends the root AGENTS.md.

These scripts run in CI on every MR. Treat them like production code:

- Type annotations on every public function.
- Tests in `tools/scripts/tests/`.
- Black-box behaviour stable: the pre-commit + CI pipelines depend on
  exit codes and output format. Don't change them without a heads-up to
  the platform-team channel.

Side-effecting scripts (audit logs, deploy hooks) must be idempotent:
safe to run twice.
