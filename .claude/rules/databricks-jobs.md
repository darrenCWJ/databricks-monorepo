---
paths:
  - "**/bundle.yml"
  - "**/databricks.yml"
  - "apps/**"
---
# Databricks Jobs Rules

## Job Clusters (not all-purpose)

- ALWAYS use `job_cluster_key` for production jobs — never all-purpose clusters.
- Reuse one job cluster across multiple tasks within the same job.
- Set `autoscale: { min_workers: N, max_workers: M }` for variable workloads.
- Use `first_on_demand: 1` with spot instances for cost savings.

## Scheduling

- Use Quartz cron format: `seconds minutes hours day-of-month month day-of-week`.
- ALWAYS specify `timezone_id` (e.g., `"Asia/Singapore"`).
- Pause non-prod schedules: `pause_status: ${if(bundle.target == "prod", "UNPAUSED", "PAUSED")}`.
- Queue runs instead of skipping: `queue: { enabled: true }`.

## Task Dependencies

- Define DAG with `depends_on: [{ task_key: "upstream_task" }]`.
- Use `run_if: ALL_SUCCESS` (default) for standard flows.
- Use `run_if: ALL_DONE` for cleanup/notification tasks that must always run.
- Never create circular dependencies.

## Error Handling & Retries

- Set `timeout_seconds` on every job (no infinite runs).
- Configure retries: `max_retries: 3`, `min_retry_interval_millis: 30000`.
- Set `retry_on_timeout: true` for transient failures.
- Configure `email_notifications.on_failure` for all production jobs.
- Use health rules for duration monitoring:
  ```yaml
  health:
    rules:
      - metric: RUN_DURATION_SECONDS
        op: GREATER_THAN
        value: 3600
  ```

## Security

- `run_as: { service_principal_name: ... }` on every non-dev target (SOC2).
- Never hardcode service principal IDs — use `${var.staging_sp}`.
- Secrets via `dbutils.secrets.get(scope, key)`, never in code or config.
- Set minimal permissions: `CAN_VIEW` for analysts, `CAN_MANAGE_RUN` for engineers.

## Cost Optimization

- Prefer job clusters over all-purpose (auto-terminated after job).
- Use serverless compute for lightweight notebook/Python tasks (omit cluster config).
- Scale clusters per environment: `num_workers: ${if(bundle.target == "prod", 8, 2)}`.
- For serverless environments, set `spec.client: "4"` (required).

## Path Resolution in DABs

- In `resources/*.yml` files: use `../src/...` (relative to resource file).
- In `databricks.yml` targets: use `./src/...` (relative to bundle root).
- Never use absolute workspace paths — let DAB resolve them.

## Multi-Task Orchestration Patterns

- ETL: extract tasks in parallel → transform (depends on all extracts) → load.
- Use `for_each_task` for parallel processing of collections.
- Use `run_job_task` for cross-job orchestration.
- Set `max_concurrent_runs: 1` unless parallelism is intentional.
