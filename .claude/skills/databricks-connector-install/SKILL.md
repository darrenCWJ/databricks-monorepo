---
name: databricks-connector-install
description: >
  Bootstrap a Databricks development environment — installs prerequisites
  (Databricks CLI, uv), configures workspace authentication, and verifies
  connectivity. Handles multiple workspaces with org-detection.
  TRIGGER when: user says "install databricks", "set up databricks",
  "databricks connector", "connect to databricks", "set up my dev
  environment for Databricks", or asks how to get started with Databricks.
  Also triggers when adding a new workspace to an existing setup.
  SKIP: user only wants to switch profiles (use databricks-config), query
  data (use databricks-lakebase), or run SQL (use databricks-dbsql).
version: 1.0.0
tags: [databricks, install, connector, cli, sdk, auth, setup]
---

# Databricks Connector Install

When this skill triggers, execute the steps below IN ORDER.

## Step 1 — Run the environment scan script

This skill includes a scan script at `references/scan-environment.sh`.
You MUST run it as the FIRST action. It checks all known install locations
because `which` does not work reliably in sandboxed environments.

**Find and run the script:**
```bash
find . "$HOME/.claude" -name "scan-environment.sh" -path "*databricks-connector-install*" 2>/dev/null | head -1
```

Then execute the path returned:
```bash
bash <PATH_FROM_ABOVE>
```

**Interpreting results:**
- Lines with `FOUND:` = tool IS installed at that path
- Sections with no `FOUND:` lines = tool is genuinely missing
- `SCAN_DONE:toolname` = that tool's scan completed (confirms the script ran)
- If output does NOT contain `SCAN COMPLETE` at the end, the script didn't finish

**If the script cannot be found**, run this inline fallback:
```bash
echo "=== DATABRICKS ===" && for p in /opt/homebrew/bin/databricks "$HOME/.local/bin/databricks" /usr/local/bin/databricks; do "$p" --version >/dev/null 2>&1 && echo "FOUND: $p version=$($p --version 2>&1)"; done && echo "=== UV ===" && for p in /opt/homebrew/bin/uv "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv" /usr/local/bin/uv; do "$p" --version >/dev/null 2>&1 && echo "FOUND: $p version=$($p --version 2>&1)"; done && echo "=== BREW ===" && for p in /opt/homebrew/bin/brew /usr/local/bin/brew; do "$p" --version >/dev/null 2>&1 && echo "FOUND: $p"; done && echo "=== GIT ===" && for p in /usr/bin/git /opt/homebrew/bin/git; do "$p" --version >/dev/null 2>&1 && echo "FOUND: $p version=$($p --version 2>&1)"; done && echo "=== PROFILES ===" && grep -E "^\[|^host|^auth_type" "$HOME/.databrickscfg" 2>/dev/null && echo "=== AI DEV KIT ===" && cat "$HOME/.ai-dev-kit/version" 2>/dev/null && echo "=== SCAN COMPLETE ==="
```

## IMPORTANT: Do NOT trust `which` results

If you ran `which <tool>` and it said "not found" — that does NOT mean the
tool is missing. `which` fails in sandboxed shells. The scan script above
is the ONLY reliable way to determine what is installed.

If you already ran `which` before reading this: IGNORE those results and
run the scan script anyway.

## Step 2 — Present environment summary

After the scan completes, show the user TWO things:

**A) Components table** — all tools, their paths, versions, and status:

> **Installed Components:**
> | Tool | Path | Version | Status |
> |------|------|---------|--------|
> | Databricks CLI | /opt/homebrew/bin/databricks | v0.299.0 | OK |
> | uv | /opt/homebrew/bin/uv | v0.11.11 | OK |
> | Homebrew | /opt/homebrew/bin/brew | — | OK |
> | git | /usr/bin/git | v2.50.1 | OK |
> | AI Dev Kit | ~/.ai-dev-kit/ | v0.1.10 | OK |

If a tool is missing, show it as:
> | uv | — | — | MISSING |

If multiple installations exist for one tool, list all and note which is selected.

**B) Databricks environment** — parse profile names, hosts, and auth types
from the scan output (NEVER display tokens or secrets) and show:

> **Databricks Environment:**
> | Profile | Host | Auth Type | Status | Default |
> |---------|------|-----------|--------|---------|
> | DEFAULT | https://workspace.cloud.databricks.com | token (PAT) | — | |
> | Darren Chua | https://workspace.cloud.databricks.com | databricks-cli (OAuth) | — | * |
>
> Workspace: GovTech UAT
> Default profile: Darren Chua

If CLI was not found, skip the profiles table and note:
> "Cannot show profiles — Databricks CLI not installed."

## Step 3 — Ask user what to do next

After showing both tables, ask:

> "What would you like to do?
> 1. **Install missing tools** — [list what's missing, or 'everything is installed']
> 2. **Add a new workspace** — connect to another Databricks workspace
> 3. **Verify connection** — test that the current profile works
> 4. **Nothing** — stop here"

Do NOT install anything without the user choosing.

## Step 4 — Install (only if user chose to install)

Refer to `references/install-guide.md` for install commands, auth setup,
and verification steps (Phase 1 onwards).

## Rules

- NEVER report a tool as missing based only on `which` failing
- NEVER install without completing Steps 1-4 first
- NEVER install without user consent
- Use FULL ABSOLUTE PATHS for all commands after a tool is found
- Do NOT execute remote scripts (no curl|sh)
