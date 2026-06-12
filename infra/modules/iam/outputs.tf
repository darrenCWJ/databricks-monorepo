output "group_ids" {
  description = "Map of group keys to their Databricks group IDs"
  value       = { for k, g in databricks_group.groups : k => g.id }
}

output "group_names" {
  description = "Map of group keys to their Databricks display names"
  value       = { for k, g in databricks_group.groups : k => g.display_name }
}

output "user_ids" {
  description = "Map of user keys to their Databricks user IDs"
  value       = { for k, u in databricks_user.users : k => u.id }
}

output "service_principal_ids" {
  description = "Map of service principal keys to their Databricks SP IDs"
  value       = { for k, sp in databricks_service_principal.sps : k => sp.id }
}

output "service_principal_application_ids" {
  description = "Map of service principal keys to their application IDs (used as principal in UC grants)"
  value       = { for k, sp in databricks_service_principal.sps : k => sp.application_id }
}
