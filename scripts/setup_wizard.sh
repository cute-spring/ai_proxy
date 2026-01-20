#!/bin/bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

die() { echo -e "${RED}$1${NC}"; exit 1; }
warn() { echo -e "${YELLOW}$1${NC}"; }
info() { echo -e "${GREEN}$1${NC}"; }

prompt() {
  local label="$1"
  local default="${2:-}"
  local value=""
  if [ -n "$default" ]; then
    read -r -p "$label [$default]: " value
    if [ -z "$value" ]; then value="$default"; fi
  else
    read -r -p "$label: " value
  fi
  printf '%s' "$value"
}

prompt_secret() {
  local label="$1"
  local value=""
  read -r -s -p "$label: " value
  echo ""
  printf '%s' "$value"
}

prompt_yn() {
  local label="$1"
  local default="${2:-y}"
  local value=""
  read -r -p "$label (y/n) [$default]: " value
  if [ -z "$value" ]; then value="$default"; fi
  case "$value" in
    y|Y) return 0 ;;
    n|N) return 1 ;;
    *) warn "请输入 y 或 n"; prompt_yn "$label" "$default" ;;
  esac
}

random_key() {
  if command -v python3 >/dev/null 2>&1; then
    python3 - <<'PY'
import secrets
print("sk-" + secrets.token_urlsafe(24))
PY
    return 0
  fi
  printf 'sk-%s\n' "$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 32)"
}

write_env() {
  local env_path="$1"
  shift
  : > "$env_path"
  for kv in "$@"; do
    local key="${kv%%=*}"
    local value="${kv#*=}"
    printf '%s=%q\n' "$key" "$value" >> "$env_path"
  done
}

append_yaml() {
  local yaml_path="$1"
  shift
  printf '%s\n' "$@" >> "$yaml_path"
}

ensure_file_exists_if_set() {
  local label="$1"
  local path="${2:-}"
  if [ -n "$path" ] && [ ! -f "$path" ]; then
    die "错误: $label 文件不存在 -> $path"
  fi
}

info "LiteLLM Proxy 配置向导启动"

ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env}"
CONFIG_FILE="${CONFIG_FILE:-$ROOT_DIR/config.yaml}"

LITELLM_HOST="$(prompt "LiteLLM 监听地址 (host)" "${LITELLM_HOST:-0.0.0.0}")"
LITELLM_PORT="$(prompt "LiteLLM 监听端口 (port)" "${LITELLM_PORT:-4000}")"

SSL_CERT_FILE_VALUE="$(prompt "企业 CA 证书路径 (可留空)" "${SSL_CERT_FILE:-}")"
if [ -n "$SSL_CERT_FILE_VALUE" ]; then
  ensure_file_exists_if_set "CA 证书" "$SSL_CERT_FILE_VALUE"
fi

MASTER_KEY_VALUE="$(prompt "代理 Master Key (留空自动生成)" "${LITELLM_MASTER_KEY:-}")"
if [ -z "$MASTER_KEY_VALUE" ]; then
  MASTER_KEY_VALUE="$(random_key)"
  info "已生成 Master Key（已写入 .env）"
fi

AZURE_ENABLE=0
VERTEX_ENABLE=0
QWEN_ENABLE=0

if prompt_yn "是否启用 Azure OpenAI" "y"; then AZURE_ENABLE=1; fi
if prompt_yn "是否启用 Vertex AI Gemini" "y"; then VERTEX_ENABLE=1; fi
if prompt_yn "是否启用 Qwen (DashScope)" "y"; then QWEN_ENABLE=1; fi

AZURE_CLIENT_ID_VALUE=""
AZURE_CLIENT_SECRET_VALUE=""
AZURE_TENANT_ID_VALUE=""
AZURE_API_BASE_VALUE=""
AZURE_API_VERSION_VALUE="2024-02-15-preview"
AZURE_PROXY_VALUE=""

AZURE_DEPLOY_GPT4=""
AZURE_DEPLOY_GPT41=""
AZURE_DEPLOY_GPT41_MINI=""
AZURE_DEPLOY_GPT5=""
AZURE_DEPLOY_GPT5_MINI=""
AZURE_DEPLOY_GPT5_NANO=""

if [ "$AZURE_ENABLE" = "1" ]; then
  info "Azure OpenAI 配置"
  AZURE_CLIENT_ID_VALUE="$(prompt "AZURE_CLIENT_ID")"
  AZURE_CLIENT_SECRET_VALUE="$(prompt_secret "AZURE_CLIENT_SECRET")"
  AZURE_TENANT_ID_VALUE="$(prompt "AZURE_TENANT_ID")"
  AZURE_API_BASE_VALUE="$(prompt "Azure OpenAI Endpoint (api_base，例如 https://xxx.openai.azure.com/)")"
  AZURE_API_VERSION_VALUE="$(prompt "Azure API Version" "$AZURE_API_VERSION_VALUE")"
  AZURE_PROXY_VALUE="$(prompt "Azure 出口代理 (AZURE_PROXY，可留空)" "${AZURE_PROXY:-}")"

  AZURE_DEPLOY_GPT4="$(prompt "Azure Deployment 名称 (gpt-4，可留空跳过)" "")"
  AZURE_DEPLOY_GPT41="$(prompt "Azure Deployment 名称 (gpt-4.1，可留空跳过)" "")"
  AZURE_DEPLOY_GPT41_MINI="$(prompt "Azure Deployment 名称 (gpt-4.1-mini，可留空跳过)" "")"
  AZURE_DEPLOY_GPT5="$(prompt "Azure Deployment 名称 (gpt-5，可留空跳过)" "")"
  AZURE_DEPLOY_GPT5_MINI="$(prompt "Azure Deployment 名称 (gpt-5-mini，可留空跳过)" "")"
  AZURE_DEPLOY_GPT5_NANO="$(prompt "Azure Deployment 名称 (gpt-5-nano，可留空跳过)" "")"
fi

VERTEX_PROJECT_VALUE=""
VERTEX_LOCATION_VALUE=""
GEMINI_PROXY_VALUE=""
GOOGLE_APPLICATION_CREDENTIALS_VALUE=""

if [ "$VERTEX_ENABLE" = "1" ]; then
  info "Vertex AI Gemini 配置"
  VERTEX_PROJECT_VALUE="$(prompt "VERTEX_PROJECT (GCP Project ID)" "${VERTEX_PROJECT:-}")"
  VERTEX_LOCATION_VALUE="$(prompt "VERTEX_LOCATION (例如 us-central1)" "${VERTEX_LOCATION:-us-central1}")"
  GEMINI_PROXY_VALUE="$(prompt "Gemini 出口代理 (GEMINI_PROXY，可留空)" "${GEMINI_PROXY:-}")"
  GOOGLE_APPLICATION_CREDENTIALS_VALUE="$(prompt "Service Account JSON 路径 (GOOGLE_APPLICATION_CREDENTIALS，可留空使用 gcloud ADC)" "${GOOGLE_APPLICATION_CREDENTIALS:-}")"
  if [ -n "$GOOGLE_APPLICATION_CREDENTIALS_VALUE" ]; then
    ensure_file_exists_if_set "Service Account JSON" "$GOOGLE_APPLICATION_CREDENTIALS_VALUE"
  fi
fi

DASHSCOPE_API_KEY_VALUE=""
QWEN_PROXY_VALUE=""
if [ "$QWEN_ENABLE" = "1" ]; then
  info "Qwen (DashScope) 配置"
  DASHSCOPE_API_KEY_VALUE="$(prompt_secret "DASHSCOPE_API_KEY")"
  QWEN_PROXY_VALUE="$(prompt "Qwen 出口代理 (QWEN_PROXY，可留空)" "${QWEN_PROXY:-}")"
fi

NO_PROXY_VALUE="$(prompt "NO_PROXY (可留空)" "${NO_PROXY:-localhost,127.0.0.1,0.0.0.0}")"

ENV_KVS=(
  "LITELLM_HOST=$LITELLM_HOST"
  "LITELLM_PORT=$LITELLM_PORT"
  "SSL_CERT_FILE=$SSL_CERT_FILE_VALUE"
  "LITELLM_MASTER_KEY=$MASTER_KEY_VALUE"
  "NO_PROXY=$NO_PROXY_VALUE"
)

if [ "$AZURE_ENABLE" = "1" ]; then
  ENV_KVS+=(
    "AZURE_CLIENT_ID=$AZURE_CLIENT_ID_VALUE"
    "AZURE_CLIENT_SECRET=$AZURE_CLIENT_SECRET_VALUE"
    "AZURE_TENANT_ID=$AZURE_TENANT_ID_VALUE"
    "AZURE_PROXY=$AZURE_PROXY_VALUE"
  )
fi

if [ "$VERTEX_ENABLE" = "1" ]; then
  ENV_KVS+=(
    "VERTEX_PROJECT=$VERTEX_PROJECT_VALUE"
    "VERTEX_LOCATION=$VERTEX_LOCATION_VALUE"
    "GEMINI_PROXY=$GEMINI_PROXY_VALUE"
    "GOOGLE_APPLICATION_CREDENTIALS=$GOOGLE_APPLICATION_CREDENTIALS_VALUE"
  )
fi

if [ "$QWEN_ENABLE" = "1" ]; then
  ENV_KVS+=(
    "DASHSCOPE_API_KEY=$DASHSCOPE_API_KEY_VALUE"
    "QWEN_PROXY=$QWEN_PROXY_VALUE"
  )
fi

write_env "$ENV_FILE" "${ENV_KVS[@]}"
info "已写入环境变量文件: $ENV_FILE"

: > "$CONFIG_FILE"
append_yaml "$CONFIG_FILE" "model_list:"

add_azure_model() {
  local name="$1"
  local deployment="$2"
  if [ -z "$deployment" ]; then return 0; fi
  append_yaml "$CONFIG_FILE" "  - model_name: $name"
  append_yaml "$CONFIG_FILE" "    litellm_params:"
  append_yaml "$CONFIG_FILE" "      model: azure/$deployment"
  append_yaml "$CONFIG_FILE" "      api_base: $AZURE_API_BASE_VALUE"
  append_yaml "$CONFIG_FILE" "      api_version: \"$AZURE_API_VERSION_VALUE\""
  append_yaml "$CONFIG_FILE" "      use_azure_ad: True"
  if [ -n "$SSL_CERT_FILE_VALUE" ]; then
    append_yaml "$CONFIG_FILE" "      ssl_verify: \"$SSL_CERT_FILE_VALUE\""
  fi
  if [ -n "$AZURE_PROXY_VALUE" ]; then
    append_yaml "$CONFIG_FILE" "      http_proxy: \"os.environ/AZURE_PROXY\""
  fi
  append_yaml "$CONFIG_FILE" "      rpm: 1000"
  append_yaml "$CONFIG_FILE" ""
}

if [ "$AZURE_ENABLE" = "1" ]; then
  add_azure_model "gpt-4" "$AZURE_DEPLOY_GPT4"
  add_azure_model "gpt-4.1" "$AZURE_DEPLOY_GPT41"
  add_azure_model "gpt-4.1-mini" "$AZURE_DEPLOY_GPT41_MINI"
  add_azure_model "gpt-5" "$AZURE_DEPLOY_GPT5"
  add_azure_model "gpt-5-mini" "$AZURE_DEPLOY_GPT5_MINI"
  add_azure_model "gpt-5-nano" "$AZURE_DEPLOY_GPT5_NANO"
fi

add_vertex_model() {
  local name="$1"
  local model_id="$2"
  append_yaml "$CONFIG_FILE" "  - model_name: $name"
  append_yaml "$CONFIG_FILE" "    litellm_params:"
  append_yaml "$CONFIG_FILE" "      model: vertex_ai/$model_id"
  append_yaml "$CONFIG_FILE" "      vertex_project: \"os.environ/VERTEX_PROJECT\""
  append_yaml "$CONFIG_FILE" "      vertex_location: \"os.environ/VERTEX_LOCATION\""
  if [ -n "$GEMINI_PROXY_VALUE" ]; then
    append_yaml "$CONFIG_FILE" "      http_proxy: \"os.environ/GEMINI_PROXY\""
  fi
  if [ -n "$SSL_CERT_FILE_VALUE" ]; then
    append_yaml "$CONFIG_FILE" "      ssl_verify: \"$SSL_CERT_FILE_VALUE\""
  fi
  append_yaml "$CONFIG_FILE" ""
}

if [ "$VERTEX_ENABLE" = "1" ]; then
  if prompt_yn "是否加入 gemini-1.5-pro" "y"; then add_vertex_model "gemini-pro" "gemini-1.5-pro"; fi
  if prompt_yn "是否加入 gemini-3-flash" "y"; then add_vertex_model "gemini-3-flash" "gemini-3-flash"; fi
  if prompt_yn "是否加入 gemini-3-pro" "y"; then add_vertex_model "gemini-3-pro" "gemini-3-pro"; fi
fi

if [ "$QWEN_ENABLE" = "1" ]; then
  append_yaml "$CONFIG_FILE" "  - model_name: qwen-max"
  append_yaml "$CONFIG_FILE" "    litellm_params:"
  append_yaml "$CONFIG_FILE" "      model: dashscope/qwen-max"
  append_yaml "$CONFIG_FILE" "      api_key: \"os.environ/DASHSCOPE_API_KEY\""
  if [ -n "$QWEN_PROXY_VALUE" ]; then
    append_yaml "$CONFIG_FILE" "      http_proxy: \"os.environ/QWEN_PROXY\""
  fi
  if [ -n "$SSL_CERT_FILE_VALUE" ]; then
    append_yaml "$CONFIG_FILE" "      ssl_verify: \"$SSL_CERT_FILE_VALUE\""
  fi
  append_yaml "$CONFIG_FILE" ""
fi

append_yaml "$CONFIG_FILE" "router_settings:"
append_yaml "$CONFIG_FILE" "  routing_strategy: simple-shuffle"
append_yaml "$CONFIG_FILE" "  model_group_alias:"
append_yaml "$CONFIG_FILE" "    \"default-model\": []"
append_yaml "$CONFIG_FILE" ""
append_yaml "$CONFIG_FILE" "general_settings:"
append_yaml "$CONFIG_FILE" "  master_key: $MASTER_KEY_VALUE"
append_yaml "$CONFIG_FILE" "  database_type: \"proxy_client\""
append_yaml "$CONFIG_FILE" ""
append_yaml "$CONFIG_FILE" "litellm_settings:"
append_yaml "$CONFIG_FILE" "  drop_params: True"
append_yaml "$CONFIG_FILE" "  set_verbose: False"

info "已写入配置文件: $CONFIG_FILE"

info "正在运行启动前校验（dry-run）"
ENV_FILE="$ENV_FILE" CONFIG_FILE="$CONFIG_FILE" ./start_proxy.sh --dry-run
info "校验通过"

if prompt_yn "是否安装为 macOS 开机自启服务 (launchd)" "y"; then
  if [ ! -f "$ROOT_DIR/scripts/launchd/install.sh" ]; then
    die "错误: 未找到 launchd 安装脚本: $ROOT_DIR/scripts/launchd/install.sh"
  fi
  LABEL_VALUE="$(prompt "launchd Label" "com.local.litellm.proxy")"
  LABEL="$LABEL_VALUE" PROJECT_DIR="$ROOT_DIR" "$ROOT_DIR/scripts/launchd/install.sh"
  info "launchd 已安装"
fi

if prompt_yn "是否立即启动服务（前台运行，Ctrl+C 停止）" "n"; then
  ENV_FILE="$ENV_FILE" CONFIG_FILE="$CONFIG_FILE" ./start_proxy.sh
else
  info "完成。你可以随时运行：./start_proxy.sh"
fi
