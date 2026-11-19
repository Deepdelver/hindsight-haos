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
LLM_BASE_URL=$(bashio::config 'llm_base_url')
EMBEDDINGS_PROVIDER=$(bashio::config 'embeddings_provider')
EMBEDDINGS_OPENAI_API_KEY=$(bashio::config 'embeddings_openai_api_key')
EMBEDDINGS_OPENAI_MODEL=$(bashio::config 'embeddings_openai_model')
RERANKER_PROVIDER=$(bashio::config 'reranker_provider')
MCP_ENABLED=$(bashio::config 'mcp_enabled')
MCP_LOCAL_BANK_ID=$(bashio::config 'mcp_local_bank_id')
MCP_AUTH_TOKEN=$(bashio::config 'mcp_auth_token')
WORKER_ID=$(bashio::config 'worker_id')
LOG_LEVEL=$(bashio::config 'log_level')

if [ -z "$LLM_API_KEY" ] && [ "$LLM_PROVIDER" != "ollama" ] && [ "$LLM_PROVIDER" != "llamacpp" ] && [ "$LLM_PROVIDER" != "lmstudio" ]; then
    bashio::log.error "No LLM API key configured! Go to addon Configuration and set your API key."
    bashio::log.error "Supported providers: openai, groq, anthropic, gemini, deepseek, ollama, etc."
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

    # Tune for addon use
    cat >> "$PGDATA/postgresql.conf" <<EOF
listen_addresses = '127.0.0.1'
port = 5432
shared_buffers = 128MB
work_mem = 8MB
maintenance_work_mem = 64MB
max_connections = 30
logging_collector = off
shared_preload_libraries = ''
jit = off
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
    bashio::log.warning "pgvector extension not available — Hindsight will use built-in vector support."

bashio::log.info "PostgreSQL is running."

# ---------------------------------------------------------------------------
# Configure Hindsight environment
# ---------------------------------------------------------------------------

# Database
export HINDSIGHT_API_DATABASE_URL="postgresql://hindsight@127.0.0.1:5432/hindsight"

# LLM
export HINDSIGHT_API_LLM_PROVIDER="$LLM_PROVIDER"
export HINDSIGHT_API_LLM_API_KEY="$LLM_API_KEY"
export HINDSIGHT_API_LLM_MODEL="$LLM_MODEL"
if [ -n "$LLM_BASE_URL" ]; then
    export HINDSIGHT_API_LLM_BASE_URL="$LLM_BASE_URL"
fi

# Embeddings
export HINDSIGHT_API_EMBEDDINGS_PROVIDER="$EMBEDDINGS_PROVIDER"
if [ "$EMBEDDINGS_PROVIDER" = "openai" ]; then
    if [ -n "$EMBEDDINGS_OPENAI_API_KEY" ]; then
        export HINDSIGHT_API_EMBEDDINGS_OPENAI_API_KEY="$EMBEDDINGS_OPENAI_API_KEY"
    else
        export HINDSIGHT_API_EMBEDDINGS_OPENAI_API_KEY="$LLM_API_KEY"
    fi
    if [ -n "$EMBEDDINGS_OPENAI_MODEL" ]; then
        export HINDSIGHT_API_EMBEDDINGS_OPENAI_MODEL="$EMBEDDINGS_OPENAI_MODEL"
    fi
fi

# Reranker
export HINDSIGHT_API_RERANKER_PROVIDER="$RERANKER_PROVIDER"

# MCP Server
export HINDSIGHT_API_MCP_ENABLED="$MCP_ENABLED"
export HINDSIGHT_API_MCP_LOCAL_BANK_ID="$MCP_LOCAL_BANK_ID"
if [ -n "$MCP_AUTH_TOKEN" ]; then
    export HINDSIGHT_API_MCP_AUTH_TOKEN="$MCP_AUTH_TOKEN"
fi

# Worker
export HINDSIGHT_API_WORKER_ID="$WORKER_ID"

# Server
export HINDSIGHT_API_HOST="0.0.0.0"
export HINDSIGHT_API_PORT="8888"
export HINDSIGHT_API_DATA_DIR="/data/hindsight"

# Logging
export HINDSIGHT_API_LOG_LEVEL="$LOG_LEVEL"

# Control Plane
export HINDSIGHT_CP_DATAPLANE_API_URL="http://127.0.0.1:8888"

bashio::log.info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
bashio::log.info "Configuration:"
bashio::log.info "  LLM Provider:    ${LLM_PROVIDER}"
bashio::log.info "  LLM Model:       ${LLM_MODEL}"
bashio::log.info "  Embeddings:      ${EMBEDDINGS_PROVIDER}"
bashio::log.info "  Reranker:        ${RERANKER_PROVIDER}"
bashio::log.info "  MCP Enabled:     ${MCP_ENABLED}"
bashio::log.info "  MCP Bank ID:     ${MCP_LOCAL_BANK_ID}"
bashio::log.info "  Worker ID:       ${WORKER_ID}"
bashio::log.info "  Log Level:       ${LOG_LEVEL}"
bashio::log.info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

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

# Wait a moment then report status
sleep 3
if kill -0 "$HINDSIGHT_PID" 2>/dev/null; then
    bashio::log.info "Hindsight is running! (PID: ${HINDSIGHT_PID})"
    bashio::log.info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    bashio::log.info "API:           http://0.0.0.0:8888"
    bashio::log.info "Control Plane: http://0.0.0.0:9999"
    bashio::log.info "MCP endpoint:  http://<your-ha-ip>:8888/mcp/${MCP_LOCAL_BANK_ID}/"
    bashio::log.info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
else
    bashio::log.error "Hindsight failed to start! Check the log for details."
    exit 1
fi

# Wait for the process
wait "$HINDSIGHT_PID"
