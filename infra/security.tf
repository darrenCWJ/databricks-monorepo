# ── Enhanced Security Monitoring (ESM) ────────────────────────────
# Mandatory pre-production requirement (WoG Whitelisting Security Briefing,
# measure #2): "Enable ESM on Classic Compute or use CSP for Serverless."
#
# ESM is a workspace-level toggle — it installs a security monitoring agent
# on every classic compute cluster VM in this workspace. Users retain full
# agency to create and use classic compute (personal, job, and all-purpose
# clusters); ESM adds monitoring without restricting access.
#
# Note: ESM has no effect on serverless compute, which runs in Databricks-
# managed infrastructure and is covered by Databricks' own security controls.

# resource "databricks_enhanced_security_monitoring_workspace_setting" "this" {
#   enhanced_security_monitoring_workspace {
#     is_enabled = true
#   }
# }
