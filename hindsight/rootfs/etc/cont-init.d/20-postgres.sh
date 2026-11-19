#!/usr/bin/with-contenv bashio
# shellcheck shell=bash
set -euo pipefail

# =============================================================================
# cont-init: prepare PostgreSQL cluster and Hindsight database
# =============================================================================

PGDATA="${PGDATA:-/data/pg}"
PG_MAJOR="15"
PG_BIN="/usr/lib/postgresql/${PG_MAJOR}/bin"

bashio::log.info "Preparing PostgreSQL ${PG_MAJOR}..."

# runuser switches user without PAM (plain `su` fails in HAOS addon containers).
if [ ! -f "${PGDATA}/PG_VERSION" ]; then
    bashio::log.info "Initializing a fresh cluster at ${PGDATA}"
    mkdir -p "${PGDATA}"
    chown -R postgres:postgres "${PGDATA}"
    runuser -u postgres -- "${PG_BIN}/initdb" -D "${PGDATA}" --auth=trust --encoding=UTF8 --locale=C

    cat >> "${PGDATA}/postgresql.conf" <<EOF
listen_addresses = '127.0.0.1'
port = 5432
shared_buffers = 128MB
work_mem = 8MB
maintenance_work_mem = 64MB
max_connections = 30
logging_collector = off
jit = off
EOF
    echo "host all all 127.0.0.1/32 trust" >> "${PGDATA}/pg_hba.conf"
    echo "local all all trust" >> "${PGDATA}/pg_hba.conf"
else
    bashio::log.info "Existing cluster found at ${PGDATA}"
    chown -R postgres:postgres "${PGDATA}"
fi

# The database and pgvector extension are created in the service run script,
# after PostgreSQL is started there.

bashio::log.info "PostgreSQL preparation complete"
