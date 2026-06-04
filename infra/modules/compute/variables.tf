variable "long_term_support" {
  description = "a boolean value indicating whether the runtime version with long-term support should be sued. enabled by default."
  default     = true

}

# variable "local_disk" {
#   description = "value indicating whether to let the node type be dynamic and use the latest available"
# }

variable "autotermination_minutes" {
  description = "duration before the cluster is terminated."

}

variable "cluster_name" {
  description = "name of the cluster"

}

variable "single_user_name" {
  description = "User or service principal to assign to the cluster"
  type        = string
}