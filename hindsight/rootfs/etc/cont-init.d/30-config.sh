#!/usr/bin/with-contenv bashio
# shellcheck shell=bash
set -euo pipefail

# =============================================================================
# cont-init: build the Hindsight environment from addon options
# 00-global_var.sh has already exported every option as an env var, so the
# values below are read from the environment rather than from options.json.
# =============================================================================

PG_MAJOR="15"
PG_BIN="/usr/lib/postgresql/${PG_MAJOR}/bin"
PGDATA="${PGDATA:-/data/pg}"

LLM_PROVIDER="${llm_provider:-openai}"
LLM_API_KEY="${llm_api_key:-}"
LLM_MODEL="${llm_model:-gpt-4o-mini}"
LLM_BASE_URL="${llm_base_url:-}"
EMBEDDINGS_PROVIDER="${embeddings_provider:-openai}"
EMBEDDINGS_API_KEY="${embeddings_api_key:-}"
EMBEDDINGS_MODEL="${embeddings_model:-text-embedding-3-small}"
RERANKER_PROVIDER="${reranker_provider:-rrf}"
MCP_ENABLED="${mcp_enabled:-true}"
MCP_LOCAL_BANK_ID="${mcp_local_bank_id:-default}"
MCP_AUTH_TOKEN="${mcp_auth_token:-}"
WORKER_ID="${worker_id:-hindsight-haos}"
LOG_LEVEL="${log_level:-info}"

# --- validation -------------------------------------------------------------
if [ -z "${LLM_API_KEY}" ] && [ "${LLM_PROVIDER}" != "ollama" ] && [ "${LLM_PROVIDER}" != "custom" ]; then
    bashio::log.error "llm_api_key is empty. Open the addon Configuration tab and set it."
    bashio::exit.nok
fi

# --- write the env file the service reads -----------------------------------
# Hindsight reads HINDSIGHT_API_* variables. The service script exports them,
# but writing them here keeps them in one auditable place.
mkdir -p /data/hindsight
cat > /data/hindsight/env <<EOF
HINDSIGHT_API_DATABASE_URL=postgresql://postgres@127.0.0.1:5432/hindsight
HINDSIGHT_API_LLM_PROVIDER=${LLM_PROVIDER}
HINDSIGHT_API_LLM_API_KEY=${LLM_API_KEY}
HINDSIGHT_API_LLM_MODEL=${LLM_MODEL}
HINDSIGHT_API_EMBEDDINGS_PROVIDER=${EMBEDDINGS_PROVIDER}
HINDSIGHT_API_EMBEDDINGS_OPENAI_API_KEY=${EMBEDDINGS_API_KEY:-$LLM_API_KEY}
HINDSIGHT_API_EMBEDDINGS_OPENAI_MODEL=${EMBEDDINGS_MODEL}
HINDSIGHT_API_RERANKER_PROVIDER=${RERANKER_PROVIDER}
HINDSIGHT_API_MCP_ENABLED=${MCP_ENABLED}
HINDSIGHT_API_MCP_LOCAL_BANK_ID=${MCP_LOCAL_BANK_ID}
HINDSIGHT_API_MCP_AUTH_TOKEN=${MCP_AUTH_TOKEN}
HINDSIGHT_API_WORKER_ID=${WORKER_ID}
HINDSIGHT_API_HOST=0.0.0.0
HINDSIGHT_API_PORT=8888
HINDSIGHT_API_CONTROL_PLANE_PORT=9999
HINDSIGHT_API_DATA_DIR=/data/hindsight
HINDSIGHT_API_LOG_LEVEL=${LOG_LEVEL}
HINDSIGHT_CP_DATAPLANE_API_URL=http://127.0.0.1:8888
EOF
chmod 600 /data/hindsight/env

if [ -n "${LLM_BASE_URL}" ]; then
    echo "HINDSIGHT_API_LLM_BASE_URL=${LLM_BASE_URL}" >> /data/hindsight/env
fi

bashio::log.info "Hindsight configuration written"
bashio::log.info "  LLM:        ${LLM_PROVIDER} / ${LLM_MODEL}"
bashio::log.info "  Embeddings: ${EMBEDDINGS_PROVIDER} / ${EMBEDDINGS_MODEL}"
bashio::log.info "  Reranker:   ${RERANKER_PROVIDER}"
bashio::log.info "  MCP:        ${MCP_ENABLED} (bank: ${MCP_LOCAL_BANK_ID})"
