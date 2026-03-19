#!/bin/sh
set -e

# Auto-generate a cryptographically random SECRET_KEY if not provided.
# This ensures production containers never start with an insecure default.
if [ -z "$SECRET_KEY" ]; then
    export SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    echo "INFO: No SECRET_KEY provided — generated a random key for this session."
fi

exec "$@"
