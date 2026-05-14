# Observability

## Three signals

| Signal | Lives in | Watch for |
|---|---|---|
| **Logs** | Databricks job stdout/stderr | Errors, retry storms, slow queries |
| **Metrics** | Databricks system tables + custom MLflow metrics | Row counts, freshness, drift |
| **Alerts** | Databricks SQL alerts + PagerDuty | SLA breaches, hard failures |

## Logging

- **Use the `logging` module**, not `print`. Pre-commit warns on print
  statements in `src/`.
- **Log level: INFO for happy path, WARNING for handled anomalies,
  ERROR for failures that triggered a retry.**
- **Structured logging on production-critical jobs.** JSON output;
  keys we standardise on: `event`, `app`, `task`, `txn_id`, `row_count`,
  `duration_ms`.

```python
import logging, json
log = logging.getLogger(__name__)

log.info(json.dumps({"event": "write_complete", "table": "silver_payments",
                      "row_count": rows, "duration_ms": elapsed_ms}))
```

## Metrics

- **Every job writes a row to `system.audit.deploy_events`** via
  `tools/scripts/audit_log.py` — start time, end time, table written,
  row count, status.
- **Custom metrics via MLflow** for ML jobs — model accuracy, drift,
  feature distributions.
- **Table freshness via `system.information_schema.tables`** — when was
  this table last updated.

## Alerts

| Severity | What | Goes to |
|---|---|---|
| **P1 — hard failure** | Job exit code != 0 | PagerDuty (oncall) + Slack #incidents |
| **P2 — SLA breach** | Job ran > SLA × 1.5 | Slack #data-platform |
| **P3 — anomaly** | Row count outside expected range | Slack #team-channel |
| **P4 — drift** | Schema or distribution change | Slack #team-channel |

Set these up in Databricks SQL Alerts, not in code. Alerts as code is a
nice idea, but Databricks SQL Alerts UI handles muting and acknowledgement
properly.

## Dashboards

Each team owns one operational dashboard for its pipelines. Required
panels:

- Last run status per job (green/yellow/red over 7 days).
- Row counts per output table over 30 days.
- Job duration histogram per job.
- Failed-task count per job over 7 days.

Template lives at `docs/best-practices/observability-dashboard-template.json`
(stub — fill in when first team builds theirs).

## On-call

- Each team has a primary + secondary on-call.
- On-call rotates weekly.
- First responder triages within 15 minutes for P1, 1 hour for P2.
- Run-book per known failure mode in `runbooks/incident-<mode>.md`.
