variable "grants" {
  description = "Map of UC grants keyed by an arbitrary label. Each entry targets one securable object and one principal."
  type = map(object({
    principal  = string
    securable  = string # "catalog" | "schema" | "table" | "external_location"
    name       = string # e.g. "my_catalog" or "my_catalog.bronze"
    privileges = list(string)
  }))
  default = {}
}
