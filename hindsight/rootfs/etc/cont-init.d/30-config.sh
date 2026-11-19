#!/usr/bin/with-contenv bashio
# shellcheck shell=bash
set -euo pipefail

# =============================================================================
# cont-init: translate addon options into HINDSIGHT_API_* variables.
#
# 00-global_var.sh has already exported every addon option as an environment
# variable. Only variables the hindsight-api package actually reads are written
# here; see https://hindsight.vectorize.io/developer/configuration
# =============================================================================

LLM_PROVIDER="${llm_provider:-llamacpp}"
LLM_API_KEY="${llm_api_key:-}"
LLM_MODEL="${llm_model:-gemma-4-e2b-it}"
LLM_BASE_URL="${llm_base_url:-}"
EMBEDDINGS_PROVIDER="${embeddings_provider:-onnx}"
EMBEDDINGS_API_KEY="${embeddings_api_key:-}"
EMBEDDINGS_MODEL="${embeddings_model:-intfloat/multilingual-e5-small}"
RERANKER_PROVIDER="${reranker_provider:-onnx}"
RERANKER_MODEL="${reranker_model:-hindsight-ai/hs-rerank-1}"
MCP_ENABLED="${mcp_enabled:-true}"
MCP_AUTH_TOKEN="${mcp_auth_token:-}"
WORKER_ID="${worker_id:-hindsight-haos}"
LOG_LEVEL="${log_level:-info}"
LLAMACPP_MODEL_PATH="${llamacpp_model_path:-}"
LLAMACPP_CONTEXT_SIZE="${llamacpp_context_size:-16384}"
LLAMACPP_GPU_LAYERS="${llamacpp_gpu_layers:-0}"

# Local providers need no API key. Everything else does.
NO_KEY_PROVIDERS=" llamacpp ollama lmstudio custom "
if [[ -z "$LLM_API_KEY" && "$NO_KEY_PROVIDERS" != *" $LLM_PROVIDER "* ]]; then
    bashio::log.error "llm_api_key is empty. Set it in the addon Configuration tab, or choose a local provider (llamacpp, ollama, lmstudio, custom)."
    bashio::exit.nok
fi

mkdir -p /data/hindsight
ENV_FILE=/data/hindsight/env

{
    echo "HINDSIGHT_API_DATABASE_URL=postgresql://postgres@127.0.0.1:5432/hindsight"
    printf 'HINDSIGHT_API_LLM_PROVIDER=%s\n' "$LLM_PROVIDER"
    printf 'HINDSIGHT_API_LLM_MODEL=%s\n' "$LLM_MODEL"
    printf 'HINDSIGHT_API_EMBEDDINGS_PROVIDER=%s\n' "$EMBEDDINGS_PROVIDER"
    printf 'HINDSIGHT_API_RERANKER_PROVIDER=%s\n' "$RERANKER_PROVIDER"
    printf 'HINDSIGHT_API_MCP_ENABLED=%s\n' "$MCP_ENABLED"
    printf 'HINDSIGHT_API_WORKER_ID=%s\n' "$WORKER_ID"
    echo "HINDSIGHT_API_HOST=0.0.0.0"
    echo "HINDSIGHT_API_PORT=8888"
    printf 'HINDSIGHT_API_LOG_LEVEL=%s\n' "$LOG_LEVEL"

    if [[ -n "$LLM_API_KEY" ]]; then
        printf 'HINDSIGHT_API_LLM_API_KEY=%s\n' "$LLM_API_KEY"
    fi
    if [[ -n "$LLM_BASE_URL" ]]; then
        printf 'HINDSIGHT_API_LLM_BASE_URL=%s\n' "$LLM_BASE_URL"
    fi
    if [[ -n "$MCP_AUTH_TOKEN" ]]; then
        printf 'HINDSIGHT_API_MCP_AUTH_TOKEN=%s\n' "$MCP_AUTH_TOKEN"
    fi

    case "$EMBEDDINGS_PROVIDER" in
        onnx)
            printf 'HINDSIGHT_API_EMBEDDINGS_ONNX_MODEL_ID=%s\n' "$EMBEDDINGS_MODEL"
            ;;
        local)
            printf 'HINDSIGHT_API_EMBEDDINGS_LOCAL_MODEL=%s\n' "$EMBEDDINGS_MODEL"
            ;;
        openai)
            printf 'HINDSIGHT_API_EMBEDDINGS_OPENAI_MODEL=%s\n' "$EMBEDDINGS_MODEL"
            printf 'HINDSIGHT_API_EMBEDDINGS_OPENAI_API_KEY=%s\n' "${EMBEDDINGS_API_KEY:-$LLM_API_KEY}"
            ;;
    esac

    case "$RERANKER_PROVIDER" in
        onnx)
            printf 'HINDSIGHT_API_RERANKER_ONNX_MODEL_ID=%s\n' "$RERANKER_MODEL"
            ;;
        flashrank)
            printf 'HINDSIGHT_API_RERANKER_FLASHRANK_MODEL=%s\n' "$RERANKER_MODEL"
            ;;
    esac

    if [[ "$LLM_PROVIDER" == "llamacpp" ]]; then
        printf 'HINDSIGHT_API_LLAMACPP_GPU_LAYERS=%s\n' "$LLAMACPP_GPU_LAYERS"
        printf 'HINDSIGHT_API_LLAMACPP_CONTEXT_SIZE=%s\n' "$LLAMACPP_CONTEXT_SIZE"
        if [[ -n "$LLAMACPP_MODEL_PATH" ]]; then
            printf 'HINDSIGHT_API_LLAMACPP_MODEL_PATH=%s\n' "$LLAMACPP_MODEL_PATH"
        fi
        # Keep completion budget inside the local context window.
        echo "HINDSIGHT_API_RETAIN_MAX_COMPLETION_TOKENS=8192"
        echo "HINDSIGHT_API_LLM_MAX_CONCURRENT=2"
    fi

    # Optional passthrough for any other HINDSIGHT_API_* setting.
    while IFS= read -r item; do
        [[ -z "$item" ]] && continue
        if [[ "$item" == *=* ]]; then
            key="${item%%=*}"
            value="${item#*=}"
        else
            key="$(jq -r '.name // empty' <<< "$item")"
            value="$(jq -r '.value // empty' <<< "$item")"
        fi
        [[ -n "$key" && "$key" == HINDSIGHT_API_* ]] || continue
        printf 'HINDSIGHT_API_%s=%s\n' "${key#HINDSIGHT_API_}" "$value"
    done < <(bashio::config 'env_vars' | jq -c '.[]')
} > "$ENV_FILE"

chmod 600 "$ENV_FILE"

bashio::log.info "Hindsight configuration written"
bashio::log.info "  LLM:        ${LLM_PROVIDER} / ${LLM_MODEL}"
bashio::log.info "  Embeddings: ${EMBEDDINGS_PROVIDER} / ${EMBEDDINGS_MODEL}"
bashio::log.info "  Reranker:   ${RERANKER_PROVIDER} / ${RERANKER_MODEL}"
bashio::log.info "  MCP:        ${MCP_ENABLED} at /mcp/<bank_id>/"
