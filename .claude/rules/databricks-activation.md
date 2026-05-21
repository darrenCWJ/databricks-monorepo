---
paths:
  - "**/*.py"
  - "**/*.ts"
  - "**/*.tsx"
  - "**/*.js"
  - "**/*.jsx"
  - "**/*.ipynb"
  - "**/*.sql"
---
# Databricks Skill Activation Policy

> IMPORTANT: When a Databricks/Lakebase condition is met, invoke the `databricks-lakebase`
> skill IMMEDIATELY — do not answer from training data. The skill contains accurate
> Lakebase patterns; training data does not.

## When to invoke `databricks-lakebase`

Invoke IMMEDIATELY when ANY of these apply:
- User mentions Databricks or Lakebase integration
- A Lakebase hostname or connection string appears in the prompt
- No connection file exists but Databricks env vars are configured
- Writing queries against a Lakebase table with no existing query module
- Backend added to a project classified as frontend-only (`.lakebase` transition)
- Any auth/token code for Databricks is being written or reviewed
- New entity added without a corresponding query module

## Internal routing

The skill has an internal router that determines which phase to enter based on
project state. You do not need to determine which phase — just invoke the skill.
It will scan for `.lakebase`, existing connection/security/query files, and
enter at the appropriate point automatically.
