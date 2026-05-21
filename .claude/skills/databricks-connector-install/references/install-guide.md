# Databricks Connector Install Guide

## Phase 0 — Environment Scan (Silent)

Scan the system WITHOUT asking questions. Tools installed via package managers
or user-local paths are often NOT on the sandboxed shell's PATH. Always check
known installation paths as fallbacks.

| Target | Primary check | Fallback paths (check if primary fails) |
|--------|--------------|------------------------------------------|
| OS | `uname -s` | — |
| git | `which git` | `/usr/bin/git`, `/opt/homebrew/bin/git` |
| Homebrew (macOS) | `which brew` | `/opt/homebrew/bin/brew`, `/usr/local/bin/brew` |
| Databricks CLI | `which databricks` | `/opt/homebrew/bin/databricks`, `~/.local/bin/databricks` |
| uv | `which uv` | `~/.local/bin/uv`, `~/.cargo/bin/uv`, `/opt/homebrew/bin/uv` |
| `~/.databrickscfg` | Read file, parse `[profile]` sections | — |
| `~/.ai-dev-kit/` | Check directory exists, read `version` file | — |

**Implementation pattern** — check ALL known paths for each tool, not just the
first match:

```bash
# Example: find ALL databricks CLI installations
for p in $(which databricks 2>/dev/null) /opt/homebrew/bin/databricks ~/.local/bin/databricks; do
  [ -x "$p" ] && echo "$p: $($p --version 2>&1)"
done
```

Do NOT assume `which` failure means the tool is absent. Do NOT stop at the
first match — collect all installations so duplicates are surfaced.

### Handling Multiple Installations

When more than one installation of the same tool is found:

1. **Show all found installations** with their paths and versions
2. **Ask the user which one to use** — they may have a preference (e.g., brew-managed
   for auto-updates vs pip-installed for version pinning)
3. **Record the chosen path** in internal state for use in subsequent phases

Example prompt when duplicates are found:

> "I found multiple installations of Databricks CLI:
>
> | # | Path | Version | Source |
> |---|------|---------|--------|
> | 1 | /opt/homebrew/bin/databricks | 0.299.0 | Homebrew |
> | 2 | ~/.local/bin/databricks | 0.285.0 | pip |
>
> Which would you like to use? (Homebrew-managed versions auto-update with
> `brew upgrade`; pip versions stay pinned until manually updated.)"

If versions differ significantly (e.g., one is below the minimum 0.278.0),
note which ones meet requirements and which don't.

### Internal State

Produce internal state (do not show to user):

```
os: darwin | linux | windows
has_git: bool
has_cli: bool
cli_installations: list[{path, version, source}]  # ALL found
cli_selected: {path, version} | null               # user's choice (or sole match)
has_uv: bool
uv_installations: list[{path, version, source}]
uv_selected: {path, version} | null
has_brew: bool (macOS only)
brew_path: string | null
has_ai_dev_kit: bool
ai_dev_kit_version: string | null
existing_profiles: list[{name, host, auth_type}]
```

Use this state to determine which phases to skip. When only one installation
exists for a tool, auto-select it without prompting.

### After Selection — Using the Chosen Path

Once a tool is selected (by user choice or auto-selected as the sole match):

1. **Use the full path for all subsequent commands.** Do not rely on bare
   command names (e.g., use `/opt/homebrew/bin/databricks workspace list /`
   instead of `databricks workspace list /`).
2. **Version check against minimum.** If the selected version is below the
   minimum (e.g., CLI < 0.278.0), offer to upgrade it via the appropriate
   package manager for that installation source (brew upgrade for Homebrew,
   pip install --upgrade for pip).
3. **Report the selection in the prerequisites summary** so the user has a
   record of what's being used:

> **Using:**
> | Tool | Path | Version |
> |------|------|---------|
> | Databricks CLI | /opt/homebrew/bin/databricks | 0.299.0 |
> | uv | ~/.local/bin/uv | 0.11.11 |

4. **Offer to persist the selection.** Ask the user:

> "Would you like to:
> 1. **This session only** — I'll use the full path in commands today, nothing
>    is saved
> 2. **This project only** — I'll save the paths to this project's `.env` or
>    CLAUDE.md so they're used when working in this repo
> 3. **Add to your PATH globally** — I'll add the directory to your shell
>    config (~/.zshrc or ~/.bashrc) so the tool is always available by name
>    everywhere"

#### Option 1 — Session only

Proceed using absolute paths for all commands. No files are modified.

#### Option 2 — Project only

Save the selected paths to the project's `.env` file:

```bash
# .env (or .env.local if .env is committed)
DATABRICKS_CLI_PATH=/opt/homebrew/bin/databricks
UV_PATH=~/.local/bin/uv
```

Or if the project uses CLAUDE.md, add a note there:

```markdown
## Tool Paths
- Databricks CLI: /opt/homebrew/bin/databricks
- uv: ~/.local/bin/uv
```

Rules for project-level persistence:
- Check if `.env` or `.env.local` already exists — append, don't overwrite
- Check for existing entries with `grep` before adding duplicates
- If `.env` is in `.gitignore`, use `.env`; otherwise use `.env.local`
- Show the exact lines that will be added and get confirmation

#### Option 3 — Global PATH

Append the parent directory to PATH in shell config:

```bash
# For zsh (macOS default)
echo 'export PATH="/opt/homebrew/bin:$PATH"' >> ~/.zshrc

# For bash
echo 'export PATH="/opt/homebrew/bin:$PATH"' >> ~/.bashrc
```

Rules for PATH modification:
- Only add the directory if it's not already in the shell config
- Show the exact line that will be added and get confirmation first
- Deduplicate — check with `grep` before appending
- Remind the user to open a new terminal or `source` the file

---

## Phase 1 — Install Prerequisites

Install ONLY what's missing. For each missing tool, provide the install
command and run it (with user confirmation for commands requiring privileges).

### 1a — uv (Python package manager, required by AI Dev Kit)

If `uv` not found:

> "Installing uv (Python package manager required by the AI Dev Kit)..."

**macOS (Homebrew):**
```bash
brew install uv
```

**pip (all platforms):**
```bash
pip install uv
```

After install, verify: `uv --version`

If already installed, report version and skip.

### 1b — Databricks CLI

If `databricks` not found OR version < 0.278.0:

**macOS (Homebrew):**
```bash
brew tap databricks/tap
brew install databricks
```

**pip (all platforms):**
```bash
pip install databricks-cli
```

**Windows (PowerShell):**
```powershell
winget install Databricks.DatabricksCLI
```

After install, verify: `databricks --version`

Minimum required version: **0.278.0**

If version is below minimum:
```bash
# macOS
brew upgrade databricks

# pip
pip install --upgrade databricks-cli
```

### 1c — Shell Completions (optional, macOS + zsh)

After CLI install on macOS:

> "For tab completion in zsh, add this to your ~/.zshrc:
> ```
> fpath+=$(brew --prefix)/share/zsh/site-functions
> autoload -Uz compinit && compinit
> ```
> Then open a new terminal. Want me to add this? (y/n)"

Only offer — do not auto-modify shell config without confirmation.

### Prerequisites Summary

After all installs, show:

> **Prerequisites ready:**
> | Tool | Version | Status |
> |------|---------|--------|
> | git | 2.x.x | OK |
> | Databricks CLI | 0.299.0 | OK |
> | uv | 0.11.x | OK |

---

## Phase 2 — Workspace Authentication

### 2a — Detect Existing Profiles

If `~/.databrickscfg` exists and has profiles:

> "I found existing Databricks profiles:
>
> | # | Profile | Host | Auth |
> |---|---------|------|------|
> | 1 | DEFAULT | https://your-workspace.cloud.databricks.com | token |
> | 2 | My Profile | https://your-workspace.cloud.databricks.com | databricks-cli |
>
> What would you like to do?
> 1. **Use existing** — verify and continue with one of these
> 2. **Add new workspace** — connect to a different Databricks workspace
> 3. **Skip** — I'll configure auth later"

If user picks "Use existing" → verify with `databricks workspace list / --profile <name>`,
then skip to Phase 3.

### Org Detection

When listing profiles, highlight workspaces from the same organization:

- Group profiles by host domain
- If multiple profiles share a domain pattern, note: "These appear to be from
  the same organization"
- Surface organization-specific workspaces (e.g., UAT, staging, production)

### 2b — New Workspace Setup

If no profiles exist OR user wants to add a new one:

> "Let's connect to your Databricks workspace.
>
> What's your workspace URL?
> (It looks like: `https://your-workspace.cloud.databricks.com`)
>
> If you don't know it, ask your Databricks admin or check your browser URL
> when logged into Databricks."

Once URL provided:

> "How would you like to authenticate?
> 1. **OAuth (recommended)** — browser-based login, tokens auto-refresh
> 2. **Personal Access Token (PAT)** — paste a token, simpler but expires
> 3. **Service Principal** — M2M auth for automation/CI (client ID + secret)"

#### Option 1 — OAuth login:

```bash
databricks auth login --host <workspace-url> -p "<profile-name>"
```

This opens a browser. After auth completes, the CLI stores credentials.

Note: This is an interactive command. Provide it to the user and explain what
will happen. Suggest they run it with `! databricks auth login --host <url> -p "<name>"`
so the output lands in the conversation.

#### Option 2 — PAT:

> "Create a Personal Access Token:
> 1. Log into Databricks → click your profile (top right) → **Settings**
> 2. Go to **Developer → Access tokens**
> 3. Click **Generate new token**
> 4. Name it (e.g., `cli-dev`) and set expiry
> 5. Copy the token"

```bash
databricks configure --token --profile "<profile-name>"
# Prompts for: host URL and token
```

#### Option 3 — Service Principal:

> "For service principal auth, you need:
> - **Client ID** (application ID of the service principal)
> - **Client Secret** (generated in Databricks)
>
> These are typically provided by your Databricks admin."

Set credentials as environment variables (avoids secrets in shell history):

```bash
export DATABRICKS_CLIENT_ID=<client-id>
export DATABRICKS_CLIENT_SECRET=<client-secret>
databricks auth login --host <workspace-url> -p "<profile-name>"
```

Clear the variables after login:
```bash
unset DATABRICKS_CLIENT_ID DATABRICKS_CLIENT_SECRET
```

### 2c — Set Default Profile

If multiple profiles exist after setup:

> "Which profile should be the default?
> (This is used when no `--profile` flag is specified)"

Update `~/.databrickscfg`:
```ini
[__settings__]
default_profile = <chosen-profile>
```

### 2d — Verify Authentication

After any auth method:

```bash
databricks workspace list / --profile "<profile-name>"
```

If successful → show workspace root listing.
If failed → diagnose:
- 401: token expired or invalid
- 403: insufficient permissions
- Network error: check URL, VPN, proxy

---

## Phase 3 — AI Dev Kit Installation (Optional)

### 3a — Check Existing Installation

If `~/.ai-dev-kit/` exists:

```bash
cat ~/.ai-dev-kit/version
```

If current → report and skip:
> "AI Dev Kit v0.1.10 is installed and up to date."

If outdated → offer update:
> "AI Dev Kit v0.1.8 is installed. Latest is v0.1.10. Update? (y/n)"

### 3b — Fresh Installation

If no AI Dev Kit found:

> "The Databricks AI Dev Kit installs skills, MCP server, and tool
> configurations.
>
> Visit the AI Dev Kit repository for installation instructions:
> https://github.com/databricks-solutions/ai-dev-kit
>
> The installer is interactive (TUI with arrow keys). Here are the
> **recommended settings**:
>
> | Step | Recommended Choice | Why |
> |------|-------------------|-----|
> | Release channel | **Stable** | Proven, fewer breaking changes |
> | Tools | **Claude Code** | Other tools (Cursor, Copilot, Codex, Gemini) are selectable but Claude Code is recommended |
> | Databricks profile | **DEFAULT** (or the profile you just configured) | Simplest setup |
> | Scope | **Global** | Skills available in all projects, not just one |
> | Skill profile | **All Skills** (34 skills) | Full access — you can always ignore ones you don't need |
> | MCP server path | **~/.ai-dev-kit** (default) | Standard location, shared across projects |
>
> Follow the instructions on the repository page to install, then come back
> and I'll verify the setup."

Note: The installer is interactive. The skill provides guidance on recommended
choices but the user must run the installer themselves. Do NOT execute remote
install scripts on behalf of the user.

---

## Phase 4 — Verification

Run all checks and report results:

### 4a — Auth Check

```bash
databricks auth profiles
```

Show active profiles and their status.

### 4b — Workspace Access

```bash
databricks workspace list /
```

Confirm workspace is reachable and user has access.

### 4c — Unity Catalog (if available)

```bash
databricks unity-catalog catalogs list
```

### 4d — MCP Server (if AI Dev Kit installed)

Verify MCP server is configured:
```bash
grep -l "databricks" ~/.claude.json 2>/dev/null
```

### 4e — Summary

> **Databricks Development Environment — Ready**
>
> | Component | Status | Details |
> |-----------|--------|---------|
> | Databricks CLI | v0.299.0 | OK |
> | uv | v0.11.11 | OK |
> | Auth profile | `<name>` | Connected to `<host>` |
> | Workspace access | OK | Can list files |
> | Unity Catalog | X catalogs available | `main`, `common`, ... |
> | AI Dev Kit | v0.1.10 | MCP server + 34 skills |
>
> **Next steps:**
> - Try: "List my SQL warehouses" or "Show tables in catalog X"
> - To add another workspace: re-invoke this skill
> - To switch profiles: use the `databricks-config` skill

---

## Phase 5 — Adding Additional Workspaces

Re-entry point when user already has a working setup and wants to connect to
another workspace.

### 5a — Show Current State

> "Current Databricks profiles:
>
> | Profile | Host | Default |
> |---------|------|---------|
> | DEFAULT | https://workspace-1.cloud.databricks.com | * |
> | staging | https://workspace-2.cloud.databricks.com | |
>
> Let's add a new workspace."

### 5b — Add New Profile

Same flow as Phase 2b:
1. Ask for workspace URL
2. Ask for auth method (OAuth / PAT / Service Principal)
3. Run auth command
4. Verify connection
5. Ask if this should become the default

### 5c — Profile Naming

> "What should I name this profile?
> (Tip: use descriptive names like `prod`, `uat`, `sandbox`, or
> `team-analytics`)"

---

## Troubleshooting

### CLI install fails (permission denied)

```bash
# Install to user-local bin (no elevated privileges needed)
mkdir -p ~/.local/bin
pip install --user databricks-cli
export PATH="$HOME/.local/bin:$PATH"
```

### Auth login fails (browser doesn't open)

- Check if you're in a headless/SSH environment
- Use PAT auth instead: `databricks configure --token --profile <name>`
- Or set `BROWSER=` env var to your browser path

### Workspace list returns 401

- Token may have expired: re-run `databricks auth login --host <url> -p <profile>`
- PAT may be revoked: generate a new one in Databricks UI
- Service principal secret may have expired: regenerate in admin settings

### AI Dev Kit installer hangs

- Ensure `uv` is installed and on PATH
- Check internet connectivity (needs GitHub access)
- Try with `--force` flag to overwrite existing installation
- Check firewall/proxy settings if behind corporate network

### MCP server not working after install

- Restart Claude Code / your editor
- Check `~/.claude.json` for `databricks` MCP server entry
- Verify Python venv: `~/.ai-dev-kit/.venv/bin/python --version`
- Re-run installer with `--force` to recreate venv
