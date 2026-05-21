# Credential Setup — Self-Serve Guides

## If no Databricks workspace:

> "You need a Databricks workspace first. Options:
> - **Free trial:** Go to https://www.databricks.com/try-databricks
> - **Organization account:** Ask your admin for workspace access
> - **GovTech:** Check if your agency has an existing workspace
>
> Once you have workspace access, come back and I'll continue the setup."

**STOP here** — do not generate code without a workspace.

## If no Lakebase project:

> "Create a Lakebase project in your workspace:
> 1. In Databricks, go to **Lakebase** (left sidebar)
> 2. Click **Create Project**
> 3. Name it (e.g., `hometongue-prod`)
> 4. Once created, you'll see a project dashboard with connection details
>
> Do you have tables already, or do you need to create them too?"

## If credentials are missing and no template was found:

> "You're missing some credentials. Ask your Databricks admin for a
> `lakebase-credentials.template` file — it has everything pre-filled for
> your team. Just drop it in your project root and I'll handle the rest.
>
> If you don't have an admin, let me know and I'll walk you through
> getting the credentials yourself."

**If the user wants to self-serve**, provide the relevant setup steps
below. Otherwise, STOP and wait for the template file.

---

## Data API setup (frontend/fullstack apps)

> "Enable the Data API on your Lakebase project:
> 1. Go to your Lakebase project
> 2. Click the **Data API** tab
> 3. Click **Enable Data API**
> 4. Copy the **REST endpoint URL** — add it to the template as `LAKEBASE_DATA_API_URL`"

---

## Service principal (external hosting + external users)

> "Create a service principal for your app:
> 1. In Databricks, go to **Settings → Identity & Access → Service principals**
> 2. Click **Add service principal** → name it (e.g., `hometongue-app`)
> 3. Click **Generate secret** — save both values immediately:
>    - **Application ID** → `DATABRICKS_CLIENT_ID` in the template
>    - **Client Secret** → `DATABRICKS_CLIENT_SECRET` in the template
>    ⚠️ The secret is shown only once — copy it now!
>
> Then grant the service principal access to your Lakebase project:
> 4. Go to your Lakebase project → **Settings → Permissions**
> 5. Add the service principal with **Can use** permission
>
> Finally, create a Postgres role for it (run in the Lakebase SQL editor):
> ```sql
> CREATE EXTENSION IF NOT EXISTS databricks_auth;
> SELECT databricks_create_role('<application-id>', 'SERVICE_PRINCIPAL');
> GRANT USAGE ON SCHEMA <schema> TO \"<application-id>\";
> GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA <schema> TO \"<application-id>\";
> GRANT USAGE ON ALL SEQUENCES IN SCHEMA <schema> TO \"<application-id>\";
> ```
> ⚠️ Replace `<schema>` with your chosen schema (e.g., `app`). Do NOT default to `public`."

---

## PAT (personal backend/script)

> "Create a Personal Access Token:
> 1. In Databricks, click your profile (top right) → **Settings**
> 2. Go to **Developer → Access tokens**
> 3. Click **Generate new token**
> 4. Set scope to **`postgres`** (NOT `sql` — that's for SQL warehouses)
> 5. Copy the token — add it to the template as `DATABRICKS_TOKEN`"

---

## PKCE OAuth App (external + internal users)

> "Register an OAuth application for your frontend:
> 1. In Databricks, go to **Settings → App connections** (or ask your admin)
> 2. Click **Add application**
> 3. Fill in:
>    - **Name:** `your-app-name`
>    - **Redirect URIs:** `http://localhost:5173/auth/callback`
>      (add your production URL too, e.g., `https://yourapp.com/auth/callback`)
>    - **Grant types:** Authorization Code
>    - **Client type:** Public (no secret — PKCE handles security)
> 4. Copy the **Client ID** — add it to the template as `VITE_DATABRICKS_CLIENT_ID`"

---

## Schema selection (ask ALL users):

> "Which database schema are your tables in?
> - Best practice is to use a **dedicated schema** (e.g., `app`, `api`, `myproject`)
> - Avoid `public` — it's the default but mixes your application tables with system/extension objects
> - If you're unsure, ask your Databricks admin — they may have already set one up for your team."

Store the schema name for use in all generated Data API paths and SQL grants.

---

## Create .env from template or values

**If template was processed (Step 0 of Phase 2b):** `.env` already exists — verify it has
all required values for the chosen connection method. If any are empty, ask the
user to get the missing values from their admin.

**If self-serve (no template found, user wants to set up themselves):**

1. Generate a blank `lakebase-credentials.template` at the project root:

```
# Lakebase Credentials — fill in the values below, then come back.
# This file will be merged into .env and deleted automatically.
# Do NOT commit this file to git.

DATABRICKS_HOST=
LAKEBASE_DATA_API_URL=
LAKEBASE_SCHEMA=
DATABRICKS_CLIENT_ID=
DATABRICKS_CLIENT_SECRET=
DATABRICKS_TOKEN=
```

2. Immediately add `lakebase-credentials.template` to `.gitignore` — do this
   BEFORE telling the user the file is ready, to prevent accidental commits
3. Tell the user: "I've created `lakebase-credentials.template` in your
   project root and added it to `.gitignore`. Fill in the values from the
   steps above, save the file, then come back and I'll finish the setup."
4. STOP and wait for the user to return
5. On the user's next message, re-run Step 0 to merge into `.env` and delete
   the template file

Also generate `.env.example` (committed — shows structure without secrets):

```bash
# .env.example
DATABRICKS_HOST=                      # Workspace URL (e.g., https://your-workspace.cloud.databricks.com)
LAKEBASE_DATA_API_URL=                # Lakebase project → Data API tab → REST endpoint
LAKEBASE_SCHEMA=                      # Database schema (e.g., app)
DATABRICKS_CLIENT_ID=                 # Service principal Application ID
DATABRICKS_CLIENT_SECRET=             # Service principal secret
DATABRICKS_TOKEN=                     # Personal Access Token (dev only)
```

**Important rules:**
- ALWAYS use `process.env.*` or `os.environ[*]` references in generated code —
  NEVER embed actual secret values in source files
- Ensure `.env` is in `.gitignore` before proceeding to Phase 3
- NEVER ask users to paste secrets into the chat — direct them to the template file
