# Secrets + config

## Three layers

| Layer | Use for | How |
|---|---|---|
| **Hardcoded in code** | Constants that never change. | A Python constant. |
| **`bundle.yml` variables** | Per-environment overrides (host, paths, cluster size). | `${var.…}` references. |
| **Databricks secret scope** | Anything sensitive (API keys, passwords, tokens). | `dbutils.secrets.get(...)`. |

Nothing else. No `.env` files. No `config.json` with passwords. No env
vars set in CI.

## Secret scopes

- **One scope per project.** Name: `cdo-<env>-<team>-<app>`.
  e.g. `cdo-prod-finance-payment-recon`.
- **Created by Terraform in `infra/terraform-databricks/`.**
  Never created by hand.
- **Access granted to one service principal only** — the one in
  `bundle.yml#targets#prod#run_as`. Engineers don't read prod secrets.

```python
# in your app
api_key = dbutils.secrets.get(
    scope="cdo-prod-finance-payment-recon",
    key="upstream-api-key",
)
```

## Config that's not secret

Use `bundle.yml` variables. Define defaults at the bundle level, override
per target:

```yaml
variables:
  retention_days:
    default: 90

targets:
  prod:
    variables:
      retention_days: 365
```

Read them in code via the entrypoint:

```python
# _main.py
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--retention-days", type=int, required=True)
args = parser.parse_args()
```

Then pass it in `bundle.yml#tasks#…#python_wheel_task#parameters`.

## What NOT to do

- **No `.env` files anywhere in the repo.** Pre-commit blocks them.
- **No secrets in `bundle.yml`.** Even `staging` secrets. Use a scope.
- **No secrets in `AGENTS.md`** — agents can read it.
- **No `print(secret)` for debugging** — it ends up in Databricks job logs
  which are auditable.

## Rotation

- **Rotate every 90 days** for production secrets (per IM8).
- **The rotation procedure is in `runbooks/rotate-a-secret.md`** (stub).
- **CI doesn't see prod secrets** — the deploy job runs under a CI
  service principal that has metadata access only.
