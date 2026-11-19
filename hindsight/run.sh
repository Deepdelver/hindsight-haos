#!/command/with-contenv bashio

# =============================================================================
# Hindsight AI Memory — Home Assistant OS Addon
# =============================================================================

bashio::log.info "Starting Hindsight AI Memory addon..."

# ---------------------------------------------------------------------------
# Read user options
# ---------------------------------------------------------------------------
LLM_PROVIDER=$(bashio::config 'llm_provider')
LLM_API_KEY=$(bashio::config 'llm_api_key')
LLM_MODEL=$(bashio::config 'llm_model')
WORKER_ID=$(bashio::config 'worker_id')

if [ -z "$LLM_API_KEY" ]; then
    bashio::log.error "No LLM API key configured! Go to addon Configuration and set your API key."
    bashio::log.error "Supported providers: openai, groq, anthropic, ollama, custom"
    exit 1
fi

# ---------------------------------------------------------------------------
# Initialize PostgreSQL (first run only)
# ---------------------------------------------------------------------------
PGDATA="/data/pg"

if [ ! -f "$PGDATA/PG_VERSION" ]; then
    bashio::log.info "Initializing PostgreSQL database (first run)..."
    chown -R hindsight:hindsight /data/pg /data/hindsight
    su - hindsight -c "initdb -D $PGDATA --auth=trust --encoding=UTF8 --locale=C"

    # Allow local connections
    echo "host all all 127.0.0.1/32 trust" >> "$PGDATA/pg_hba.conf"
    echo "local all all trust" >> "$PGDATA/pg_hba.conf"

    # Tune for addon use (low memory)
    cat >> "$PGDATA/postgresql.conf" <<EOF
listen_addresses = '127.0.0.1'
port = 5432
shared_buffers = 64MB
work_mem = 4MB
maintenance_work_mem = 32MB
max_connections = 20
logging_collector = off
EOF
    bashio::log.info "PostgreSQL initialized."
else
    bashio::log.info "PostgreSQL data directory found."
    chown -R hindsight:hindsight /data/pg /data/hindsight
fi

# ---------------------------------------------------------------------------
# Start PostgreSQL
# ---------------------------------------------------------------------------
bashio::log.info "Starting PostgreSQL..."
su - hindsight -c "pg_ctl -D $PGDATA -l /data/pg/logfile start -w -t 30"

# Create hindsight database if it doesn't exist
su - hindsight -c "psql -h 127.0.0.1 -lqt" | grep -q hindsight || \
    su - hindsight -c "createdb -h 127.0.0.1 hindsight"

# Enable pgvector extension
su - hindsight -c "psql -h 127.0.0.1 -d hindsight -c 'CREATE EXTENSION IF NOT EXISTS vector;'" 2>/dev/null || \
    bashio::log.warning "pgvector extension not available — Hindsight will use its built-in vector support."

bashio::log.info "PostgreSQL is running."

# ---------------------------------------------------------------------------
# Configure Hindsight environment
# ---------------------------------------------------------------------------
export HINDSIGHT_API_DATABASE_URL="postgresql://hindsight@127.0.0.1:5432/hindsight"
export HINDSIGHT_API_LLM_PROVIDER="$LLM_PROVIDER"
export HINDSIGHT_API_LLM_API_KEY="$LLM_API_KEY"
export HINDSIGHT_API_LLM_MODEL="$LLM_MODEL"
export HINDSIGHT_API_WORKER_ID="$WORKER_ID"
export HINDSIGHT_API_HOST="0.0.0.0"
export HINDSIGHT_API_PORT="8888"
export HINDSIGHT_API_CONTROL_PLANE_PORT="9999"
export HINDSIGHT_API_DATA_DIR="/data/hindsight"

bashio::log.info "LLM Provider: ${LLM_PROVIDER}"
bashio::log.info "LLM Model: ${LLM_MODEL}"
bashio::log.info "Worker ID: ${WORKER_ID}"
bashio::log.info "API: http://0.0.0.0:8888"
bashio::log.info "Control Plane: http://0.0.0.0:9999"
bashio::log.info "MCP endpoint: http://<your-ha-ip>:8888/mcp"

# ---------------------------------------------------------------------------
# Graceful shutdown handler
# ---------------------------------------------------------------------------
shutdown() {
    bashio::log.info "Shutting down Hindsight..."
    kill "$HINDSIGHT_PID" 2>/dev/null
    wait "$HINDSIGHT_PID" 2>/dev/null
    bashio::log.info "Stopping PostgreSQL..."
    su - hindsight -c "pg_ctl -D $PGDATA stop -m fast"
    bashio::log.info "Shutdown complete."
    exit 0
}
trap shutdown SIGTERM SIGINT

# ---------------------------------------------------------------------------
# Start Hindsight
# ---------------------------------------------------------------------------
bashio::log.info "Starting Hindsight API server..."
hindsight-api &
HINDSIGHT_PID=$!

bashio::log.info "Hindsight is running! (PID: ${HINDSIGHT_PID})"
bashio::log.info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
bashio::log.info "Connect your AI agents via MCP:"
bashio::log.info "  URL: http://<your-ha-ip>:8888/mcp"
bashio::log.info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Wait for the process
wait "$HINDSIGHT_PID"
