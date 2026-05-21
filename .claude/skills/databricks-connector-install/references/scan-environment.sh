#!/bin/bash
# Databricks environment scanner — finds ALL installations of required tools.
# Run this script as-is. Do NOT modify or rewrite it.

echo "=== DATABRICKS CLI ==="
for p in /opt/homebrew/bin/databricks "$HOME/.local/bin/databricks" /usr/local/bin/databricks $(which databricks 2>/dev/null); do
  "$p" --version >/dev/null 2>&1 && echo "FOUND: $p version=$($p --version 2>&1)"
done
echo "SCAN_DONE:databricks"

echo ""
echo "=== UV ==="
for p in /opt/homebrew/bin/uv "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv" /usr/local/bin/uv $(which uv 2>/dev/null); do
  "$p" --version >/dev/null 2>&1 && echo "FOUND: $p version=$($p --version 2>&1)"
done
echo "SCAN_DONE:uv"

echo ""
echo "=== HOMEBREW ==="
for p in /opt/homebrew/bin/brew /usr/local/bin/brew $(which brew 2>/dev/null); do
  "$p" --version >/dev/null 2>&1 && echo "FOUND: $p"
done
echo "SCAN_DONE:brew"

echo ""
echo "=== GIT ==="
for p in /usr/bin/git /opt/homebrew/bin/git $(which git 2>/dev/null); do
  "$p" --version >/dev/null 2>&1 && echo "FOUND: $p version=$($p --version 2>&1)"
done
echo "SCAN_DONE:git"

echo ""
echo "=== BROAD SEARCH ==="
find /opt /usr/local "$HOME/.local" "$HOME/.cargo" -name "databricks" -type f 2>/dev/null
find /opt /usr/local "$HOME/.local" "$HOME/.cargo" -name "uv" -type f 2>/dev/null
echo "SEARCH_DONE"

echo ""
echo "=== DATABRICKS PROFILES ==="
if [ -f "$HOME/.databrickscfg" ]; then
  grep -E "^\[|^host|^auth_type" "$HOME/.databrickscfg" 2>/dev/null
else
  echo "NO_CONFIG"
fi

echo ""
echo "=== AI DEV KIT ==="
cat "$HOME/.ai-dev-kit/version" 2>/dev/null || echo "NOT_INSTALLED"

echo ""
echo "=== SCAN COMPLETE ==="
