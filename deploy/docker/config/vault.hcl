# Vault configuration for MIRA Docker container
# File-based storage for single-node deployment

storage "file" {
  path = "/opt/vault/data"
}

listener "tcp" {
  address     = "127.0.0.1:8200"
  tls_disable = 1
}

# API address for client connections
api_addr = "http://127.0.0.1:8200"

# Disable mlock for container environments
disable_mlock = true

# Enable the web UI
ui = true

# Log to stdout for container logging
log_level = "info"
