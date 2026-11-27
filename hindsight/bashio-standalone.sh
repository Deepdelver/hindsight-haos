#!/usr/bin/env bash
# /usr/local/lib/bashio-standalone.sh
# shellcheck shell=bash
#
# Minimal bashio compatibility layer for running Home Assistant add-ons
# in standalone containers (no Supervisor).
#
# Goals:
# - Keep this add-on's scripts working outside HA Supervisor
# - Prefer ENV, optionally read /data/options.json (jq required)
# - Provide only the bashio::* functions reachable from the runtime scripts
#   and the four cont-init templates downloaded by ha_automodules.sh
#
# Usage (typical):
#   if ! bashio::supervisor.ping 2>/dev/null; then
#     # standalone behavior...
#   fi
#   source /usr/local/lib/bashio-standalone.sh

set -u

# -----------------------------------------------------------------------------
# Defaults
# -----------------------------------------------------------------------------
: "${STANDALONE_OPTIONS_JSON:=/data/options.json}"

# -----------------------------------------------------------------------------
# Color handling
# -----------------------------------------------------------------------------
_BASHIO_COLOR=1
[ ! -t 1 ] && _BASHIO_COLOR=0
[ -n "${NO_COLOR:-}" ] && _BASHIO_COLOR=0
[ "${TERM:-}" = "dumb" ] && _BASHIO_COLOR=0

_bashio_color() {
  [ "$_BASHIO_COLOR" = "1" ] || return 0
  case "${1:-}" in
    blue)    printf '\033[34m' ;;
    green)   printf '\033[32m' ;;
    yellow)  printf '\033[33m' ;;
    red)     printf '\033[31m' ;;
    magenta) printf '\033[35m' ;;
    reset)   printf '\033[0m'  ;;
    *)       printf '' ;;
  esac
}

_bashio_log() {
  local c="${1:-}"; shift || true
  printf '%s%s%s\n' "$(_bashio_color "$c")" "$*" "$(_bashio_color reset)"
}

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
_bashio_is_true() {
  case "${1:-}" in
    1|true|TRUE|True|yes|YES|Yes|on|ON|On) return 0 ;;
    *) return 1 ;;
  esac
}

# ENV mapping helper:
# tries variants + prefixes and prints the value if env var is defined (even empty),
# returning 0 when found, 1 when not found.
_bashio_env_get() {
  local key="${1:-}"
  [ -n "$key" ] || return 1

  local norm norm_uc raw_uc
  norm="$(printf '%s' "$key" | tr '.-' '__')"
  norm_uc="$(printf '%s' "$norm" | tr '[:lower:]' '[:upper:]')"
  raw_uc="$(printf '%s' "$key" | tr '[:lower:]' '[:upper:]')"

  local variants=(
    "$key"
    "$raw_uc"
    "$norm"
    "$norm_uc"
  )

  local prefixes=("" "CFG_" "CONFIG_" "ADDON_" "OPTION_" "OPT_")

  local v p name
  for v in "${variants[@]}"; do
    for p in "${prefixes[@]}"; do
      name="${p}${v}"
      if [ -n "${!name+x}" ]; then
        printf '%s' "${!name}"
        return 0
      fi
    done
  done

  return 1
}

# JSON options source (jq required). Prints value or empty; returns 0 always.
_bashio_json_get() {
  local key="${1:-}"
  local file="${STANDALONE_OPTIONS_JSON:-}"

  [ -n "$key" ] || return 0
  [ -n "$file" ] || return 0
  [ -f "$file" ] || return 0
  command -v jq >/dev/null 2>&1 || return 0

  # getpath(split(".")) supports nested access; missing => empty. Not "// empty",
  # which would also drop a boolean false
  jq -r --arg k "$key" 'getpath(($k|split("."))) | select(. != null)' "$file" 2>/dev/null || true
}

# -----------------------------------------------------------------------------
# Logging API
# -----------------------------------------------------------------------------
bashio::log.blue()    { _bashio_log blue    "$*"; }
bashio::log.green()   { _bashio_log green   "$*"; }
bashio::log.yellow()  { _bashio_log yellow  "$*"; }
bashio::log.red()     { _bashio_log red     "$*"; }
bashio::log.magenta() { _bashio_log magenta "$*"; }

# Common aliases
bashio::log.info()    { bashio::log.blue   "$@"; }
bashio::log.warning() { bashio::log.yellow "$@"; }
bashio::log.error()   { bashio::log.red    "$@"; }
bashio::log.notice()  { bashio::log.blue   "$@"; }
bashio::log.fatal()   { bashio::log.red    "$@"; }

# -----------------------------------------------------------------------------
# Supervisor shim
# -----------------------------------------------------------------------------
bashio::supervisor.ping() {
  _bashio_is_true "${STANDALONE_FORCE_SUPERVISOR_PING:-}" && return 0
  return 1
}

# No Supervisor to answer: callers see the same failure as an unreachable API
bashio::api.supervisor() { return 1; }

# -----------------------------------------------------------------------------
# Add-on metadata
# -----------------------------------------------------------------------------
bashio::app.name()         { printf '%s' "${ADDON_NAME:-Standalone container}"; }
bashio::app.description()  { printf '%s' "${ADDON_DESCRIPTION:-Running without Home Assistant Supervisor}"; }
bashio::app.version()      { printf '%s' "${BUILD_VERSION:-1.0}"; }
bashio::app.version_latest(){ printf '%s' "${ADDON_VERSION_LATEST:-${BUILD_VERSION:-1.0}}"; }

bashio::app.update_available() {
  if [ -n "${ADDON_VERSION_LATEST:-}" ] && [ "${ADDON_VERSION_LATEST:-}" != "${BUILD_VERSION:-}" ]; then
    printf '%s' "true"
  else
    printf '%s' "false"
  fi
}

bashio::app.ingress_port() { printf '%s' "${ADDON_INGRESS_PORT:-}"; }
bashio::app.ip_address()   { printf '%s' "${ADDON_IP_ADDRESS:-}"; }

# app.option : write/delete option in JSON when possible; fallback export env
bashio::app.option() {
  local key="${1:-}" value="${2-__BASHIO_UNSET__}" file="${STANDALONE_OPTIONS_JSON:-}"
  [ -n "$key" ] || return 0

  if [ -n "$file" ] && [ -f "$file" ] && command -v jq >/dev/null 2>&1; then
    local tmp
    tmp="$(mktemp)"
    if [ "$value" = "__BASHIO_UNSET__" ]; then
      jq --arg k "$key" 'delpath(($k|split(".")))' "$file" >"$tmp" && mv "$tmp" "$file"
    else
      jq --arg k "$key" --arg v "$value" 'setpath(($k|split(".")); $v)' "$file" >"$tmp" && mv "$tmp" "$file"
    fi
    return 0
  fi

  # Fallback: export as env (dot/dash -> underscore). Delete becomes no-op.
  if [ "$value" != "__BASHIO_UNSET__" ]; then
    export "$(printf '%s' "$key" | tr '.-' '__')"="$value"
  fi
}

# -----------------------------------------------------------------------------
# System info
# -----------------------------------------------------------------------------
bashio::info.operating_system() {
  if [ -r /etc/os-release ]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    printf '%s' "${PRETTY_NAME:-${NAME:-Linux}}"
  else
    printf '%s' "Linux"
  fi
}
bashio::info.arch()         { uname -m; }
bashio::info.machine()      { uname -m; }
bashio::info.homeassistant(){ printf '%s' "standalone"; }
bashio::info.supervisor()  { printf '%s' "standalone"; }

# -----------------------------------------------------------------------------
# Config API
# -----------------------------------------------------------------------------
bashio::config() {
  local key="${1:-}"
  [ -n "$key" ] || { printf '%s' ""; return 0; }

  local v=""
  if _bashio_env_get "$key" >/dev/null 2>&1; then
    v="$(_bashio_env_get "$key" 2>/dev/null || true)"
  fi
  [ -z "$v" ] && v="$(_bashio_json_get "$key")"
  printf '%s' "${v:-}"
}

bashio::config.has_value() { [ -n "$(bashio::config "$1")" ]; }

# config.false : only the value "false", like bashio (unset is not false)
bashio::config.false() { [ "$(bashio::config "$1")" = "false" ]; }

# -----------------------------------------------------------------------------
# var helpers
# -----------------------------------------------------------------------------
bashio::var.true() { _bashio_is_true "${1:-}"; }

# -----------------------------------------------------------------------------
# Exit helpers
# -----------------------------------------------------------------------------
bashio::exit.ok()  { exit 0; }
bashio::exit.nok() { local m="${1:-}"; [ -n "$m" ] && bashio::log.red "$m"; exit 1; }

