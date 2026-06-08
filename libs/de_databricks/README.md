# de_databricks

Databricks workspace admin toolkit for the CDO platform.

## Modules

- **common** — Session factories (REST, OAuth, SDK) and shared utilities
- **account** — Service principal lifecycle (create, token, git credentials)
- **iam** — SCIM group/user CRUD, permission assignments, entitlements
- **compute** — Shared cluster provisioning and permissions
- **workflow** — Job/pipeline creation and management
- **unitycatalog** — Unity Catalog permissions and catalog workspace bindings
- **housekeep** — Automated user deactivation, asset cleanup, email notifications
- **tableau** — Tableau Server group membership sync from Unity Catalog entitlements
- **setup** — Workspace onboarding (catalog, schema, volume, group creation)
- **migrate** — Full catalog replication with permission preservation

## Installation

```bash
pip install -e ".[dev]"
```

## Usage

```python
import sys
sys.path.append("/Workspace/Repos/shared/mono-dev/libs/de_databricks/src")

from de_databricks.common.session import create_databricks_session
session = create_databricks_session()
```

## Testing

Local (import smoke test):
```bash
pytest tests/
```

Integration tests run on Databricks clusters via the notebooks in `notebooks/tests/`.
