#!/bin/bash
set -e

# Check if POSTGRES_READONLY_USER and POSTGRES_READONLY_PASSWORD are defined
if [[ -z "${POSTGRES_READONLY_USER}" || -z "${POSTGRES_READONLY_PASSWORD}" ]]; then
  echo "Skipping read-only user creation because POSTGRES_READONLY_USER or POSTGRES_READONLY_PASSWORD is not set."
  exit 0
fi

# Variables from environment
readonly_user=${POSTGRES_READONLY_USER}
readonly_password=${POSTGRES_READONLY_PASSWORD}
database=${POSTGRES_DB}
schema=${SCHEMA:-public}

echo "Creating read-only user: $readonly_user"

# Create the read-only user and assign permissions
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$database" <<-EOSQL
  CREATE USER $readonly_user WITH PASSWORD '$readonly_password';
  GRANT CONNECT ON DATABASE $database TO $readonly_user;
  GRANT USAGE ON SCHEMA $schema TO $readonly_user;
  GRANT SELECT ON ALL TABLES IN SCHEMA $schema TO $readonly_user;
  GRANT SELECT ON ALL SEQUENCES IN SCHEMA $schema TO $readonly_user;
  ALTER DEFAULT PRIVILEGES IN SCHEMA $schema GRANT SELECT ON TABLES TO $readonly_user;
EOSQL
