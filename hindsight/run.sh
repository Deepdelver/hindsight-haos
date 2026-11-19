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
EMBEDDINGS_PROVIDER=$(bashio::config 'embeddings_provider')
EMBEDDINGS_MODEL=$(bashio::config 'embeddings_model')
RERANKER_PROVIDER=$(bashio::config 'reranker_provider')
MCP_ENABLED=$(bashio::config 'mcp_enabled')
MCP_LOCAL_BANK_ID=$(bashio::config 'mcp_local_bank_id')
WORKER_ID=$(bashio::config 'worker_id')
LOG_LEVEL=$(bashio::config 'log_level')

# Optional fields — bashio returns null/empty for unset str? options
LLM_BASE_URL=""
if bashio::config.has_value 'llm_base_url'; then
    LLM_BASE_URL=$(bashio::config 'llm_base_url')
fi
EMBEDDINGS_API_KEY=""
if bashio::config.has_value 'embeddings_api_key'; then
    EMBEDDINGS_API_KEY=$(bashio::config 'embeddings_api_key')
fi
MCP_AUTH_TOKEN=""
if bashio::config.has_value 'mcp_auth_token'; then
    MCP_AUTH_TOKEN=$(bashio::config 'mcp_auth_token')
fi

if [ -z "$LLM_API_KEY" ] && [ "$LLM_PROVIDER" != "ollama" ] && [ "$LLM_PROVIDER" != "custom" ]; then
    bashio::log.error "No LLM API key configured! Go to addon Configuration and set your API key."
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

    echo "host all all 127.0.0.1/32 trust" >> "$PGDATA/pg_hba.conf"
    echo "local all all trust" >> "$PGDATA/pg_hba.conf"

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

su - hindsight -c "psql -h 127.0.0.1 -lqt" | grep -q hindsight || \
    su - hindsight -c "createdb -h 127.0.0.1 hindsight"

su - hindsight -c "psql -h 127.0.0.1 -d hindsight -c 'CREATE EXTENSION IF NOT EXISTS vector;'" 2>/dev/null || \
    bashio::log.warning "pgvector extension not available."

bashio::log.info "PostgreSQL is running."

# ---------------------------------------------------------------------------
# Configure Hindsight environment
# ---------------------------------------------------------------------------
export HINDSIGHT_API_DATABASE_URL="postgresql://hindsight@127.0.0.1:5432/hindsight"
export HINDSIGHT_API_LLM_PROVIDER="$LLM_PROVIDER"
export HINDSIGHT_API_LLM_API_KEY="$LLM_API_KEY"
export HINDSIGHT_API_LLM_MODEL="$LLM_MODEL"

if [ -n "$LLM_BASE_URL" ]; then
    export HINDSIGHT_API_LLM_BASE_URL="$LLM_BASE_URL"
fi

# Embeddings — slim image has no local models, so we use external providers
export HINDSIGHT_API_EMBEDDINGS_PROVIDER="$EMBEDDINGS_PROVIDER"
if [ "$EMBEDDINGS_PROVIDER" = "openai" ]; then
    if [ -n "$EMBEDDINGS_API_KEY" ]; then
        export HINDSIGHT_API_EMBEDDINGS_OPENAI_API_KEY="$EMBEDDINGS_API_KEY"
    else
        export HINDSIGHT_API_EMBEDDINGS_OPENAI_API_KEY="$LLM_API_KEY"
    fi
    export HINDSIGHT_API_EMBEDDINGS_OPENAI_MODEL="$EMBEDDINGS_MODEL"
elif [ "$EMBEDDINGS_PROVIDER" = "ollama" ]; then
    if [ -n "$LLM_BASE_URL" ]; then
        export HINDSIGHT_API_EMBEDDINGS_OLLAMA_BASE_URL="$LLM_BASE_URL"
    fi
    export HINDSIGHT_API_EMBEDDINGS_OLLAMA_MODEL="$EMBEDDINGS_MODEL"
elif [ "$EMBEDDINGS_PROVIDER" = "cohere" ]; then
    if [ -n "$EMBEDDINGS_API_KEY" ]; then
        export HINDSIGHT_API_EMBEDDINGS_COHERE_API_KEY="$EMBEDDINGS_API_KEY"
    fi
fi

# Reranker — rrf (Reciprocal Rank Fusion) needs no ML model
export HINDSIGHT_API_RERANKER_PROVIDER="$RERANKER_PROVIDER"

# MCP Server
export HINDSIGHT_API_MCP_ENABLED="$MCP_ENABLED"
export HINDSIGHT_API_MCP_LOCAL_BANK_ID="$MCP_LOCAL_BANK_ID"
if [ -n "$MCP_AUTH_TOKEN" ]; then
    export HINDSIGHT_API_MCP_AUTH_TOKEN="$MCP_AUTH_TOKEN"
fi

# Worker, server, logging
export HINDSIGHT_API_WORKER_ID="$WORKER_ID"
export HINDSIGHT_API_HOST="0.0.0.0"
export HINDSIGHT_API_PORT="8888"
export HINDSIGHT_API_DATA_DIR="/data/hindsight"
export HINDSIGHT_API_LOG_LEVEL="$LOG_LEVEL"
export HINDSIGHT_CP_DATAPLANE_API_URL="http://127.0.0.1:8888"

bashio::log.info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
bashio::log.info "Configuration:"
bashio::log.info "  LLM Provider:    ${LLM_PROVIDER}"
bashio::log.info "  LLM Model:       ${LLM_MODEL}"
bashio::log.info "  Embeddings:      ${EMBEDDINGS_PROVIDER} (${EMBEDDINGS_MODEL})"
bashio::log.info "  Reranker:        ${RERANKER_PROVIDER}"
bashio::log.info "  MCP Enabled:     ${MCP_ENABLED}"
bashio::log.info "  MCP Bank ID:     ${MCP_LOCAL_BANK_ID}"
bashio::log.info "  Worker ID:       ${WORKER_ID}"
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

sleep 5
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

wait "$HINDSIGHT_PID"
