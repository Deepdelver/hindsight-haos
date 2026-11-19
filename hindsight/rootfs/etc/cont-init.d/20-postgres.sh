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

# Hindsight database
if ! runuser -u postgres -- "${PG_BIN}/psql" -h 127.0.0.1 -lqt 2>/dev/null | grep -q hindsight; then
    bashio::log.info "Creating hindsight database"
    runuser -u postgres -- "${PG_BIN}/createdb" -h 127.0.0.1 hindsight
fi

# pgvector — Hindsight needs a vector extension for semantic search
if ! runuser -u postgres -- "${PG_BIN}/psql" -h 127.0.0.1 -d hindsight -tAc "SELECT 1 FROM pg_extension WHERE extname='vector'" 2>/dev/null | grep -q 1; then
    bashio::log.info "Enabling pgvector extension"
    runuser -u postgres -- "${PG_BIN}/psql" -h 127.0.0.1 -d hindsight -c 'CREATE EXTENSION IF NOT EXISTS vector;' \
        || bashio::log.warning "pgvector unavailable; Hindsight may fall back to built-in search"
fi

bashio::log.info "PostgreSQL preparation complete"
