#!/bin/bash
# Vault unseal script for s6-overlay container restarts
# Simplified version without fancy output functions

export VAULT_ADDR="http://127.0.0.1:8200"

echo "vault-unseal: Checking Vault status..."

# Check if init-keys.txt exists
if [ ! -f /opt/vault/init-keys.txt ]; then
    echo "vault-unseal: ERROR - init-keys.txt missing"
    exit 1
fi

# Check seal status using vault status exit codes
# 0 = unsealed, 2 = sealed, 1 = error
# Note: do NOT use set -e because vault status returns 2 when sealed (expected)
vault status > /dev/null 2>&1
STATUS=$?

if [ $STATUS -eq 0 ]; then
    echo "vault-unseal: Vault already unsealed"
elif [ $STATUS -eq 2 ]; then
    echo "vault-unseal: Vault is sealed, unsealing..."
    UNSEAL_KEY=$(grep "Unseal Key 1" /opt/vault/init-keys.txt | awk '{print $NF}')
    if [ -z "$UNSEAL_KEY" ]; then
        echo "vault-unseal: ERROR - Could not extract unseal key"
        exit 1
    fi
    vault operator unseal "$UNSEAL_KEY"
    echo "vault-unseal: Unsealed successfully"
else
    echo "vault-unseal: ERROR - Vault status check failed (exit code: $STATUS)"
    exit 1
fi

# Authenticate with root token
echo "vault-unseal: Authenticating..."
ROOT_TOKEN=$(grep "Initial Root Token" /opt/vault/init-keys.txt | awk '{print $NF}')
if [ -z "$ROOT_TOKEN" ]; then
    echo "vault-unseal: ERROR - Could not extract root token"
    exit 1
fi
vault login "$ROOT_TOKEN" > /dev/null
echo "vault-unseal: Authenticated successfully"

echo "vault-unseal: Vault is ready"
