#!/bin/bash

# =================================================================
# LiteLLM Proxy 一键启动脚本
# 功能：环境检查、证书校验、加载配置、启动服务
# =================================================================

set -euo pipefail

# 设置颜色输出
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

die() {
    echo -e "${RED}$1${NC}"
    exit 1
}

warn() {
    echo -e "${YELLOW}$1${NC}"
}

info() {
    echo -e "${GREEN}$1${NC}"
}

is_placeholder() {
    case "${1:-}" in
        ""|your-*|YOUR-*|"<"*">"*|"/path/to/"*|"https://your-"*|"http://your-"*) return 0 ;;
        *) return 1 ;;
    esac
}

require_env() {
    local name="$1"
    local value="${!name:-}"
    if [ -z "$value" ]; then
        die "错误: 环境变量 $name 未设置"
    fi
    if is_placeholder "$value"; then
        die "错误: 环境变量 $name 仍为占位值，请在 $ENV_FILE 中填写真实值"
    fi
}

echo -e "${YELLOW}正在初始化 LiteLLM Proxy 环境...${NC}"

# 1. 检查 .env 文件
ENV_FILE="${ENV_FILE:-.env}"
CONFIG_FILE="${CONFIG_FILE:-config.yaml}"
SKIP_VALIDATE="${LITELLM_SKIP_VALIDATE:-0}"
DRY_RUN=0

for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=1 ;;
        --skip-validate) SKIP_VALIDATE=1 ;;
    esac
done

if [ ! -f "$ENV_FILE" ]; then
    die "错误: 未找到 $ENV_FILE 文件！请先创建并填写凭据。"
fi

# 加载环境变量
set -a
source "$ENV_FILE"
set +a

if [ -n "${NO_PROXY:-}" ]; then
    export no_proxy="$NO_PROXY"
fi

# 2. 检查 CA 证书路径
if [ -z "${SSL_CERT_FILE:-}" ]; then
    warn "警告: SSL_CERT_FILE 未在 $ENV_FILE 中设置，将使用系统默认证书。"
else
    if [ ! -f "$SSL_CERT_FILE" ]; then
        die "错误: 证书文件不存在 -> $SSL_CERT_FILE"
    else
        info "确认: CA 证书已就绪 -> $SSL_CERT_FILE"
        export REQUESTS_CA_BUNDLE="$SSL_CERT_FILE"
        export CURL_CA_BUNDLE="$SSL_CERT_FILE"
        export SSL_CERT_FILE="$SSL_CERT_FILE"
    fi
fi

# 3. 检查并设置分模型代理 (由 config.yaml 内部引用)
if [ ! -z "${AZURE_PROXY:-}" ]; then
    if is_placeholder "$AZURE_PROXY"; then
        warn "警告: AZURE_PROXY 仍为占位值，将忽略该代理配置。"
        unset AZURE_PROXY
    else
        info "确认: 已加载 Azure 专属代理 -> $AZURE_PROXY"
    fi
fi
if [ ! -z "${GEMINI_PROXY:-}" ]; then
    if is_placeholder "$GEMINI_PROXY"; then
        warn "警告: GEMINI_PROXY 仍为占位值，将忽略该代理配置。"
        unset GEMINI_PROXY
    else
        info "确认: 已加载 Gemini 专属代理 -> $GEMINI_PROXY"
    fi
fi
if [ ! -z "${QWEN_PROXY:-}" ]; then
    if is_placeholder "$QWEN_PROXY"; then
        warn "警告: QWEN_PROXY 仍为占位值，将忽略该代理配置。"
        unset QWEN_PROXY
    else
        info "确认: 已加载 Qwen 专属代理 -> $QWEN_PROXY"
    fi
fi

# 4. 检查 config.yaml
if [ ! -f "$CONFIG_FILE" ]; then
    die "错误: 未找到 $CONFIG_FILE 配置文件！"
fi

USE_AZURE=0
USE_VERTEX=0
USE_DASHSCOPE=0
if grep -qE '^[[:space:]]*model:[[:space:]]*azure/' "$CONFIG_FILE"; then USE_AZURE=1; fi
if grep -qE '^[[:space:]]*model:[[:space:]]*vertex_ai/' "$CONFIG_FILE"; then USE_VERTEX=1; fi
if grep -qE '^[[:space:]]*model:[[:space:]]*dashscope/' "$CONFIG_FILE"; then USE_DASHSCOPE=1; fi

if [ "$SKIP_VALIDATE" != "1" ]; then
    if grep -nE 'your-azure-api-endpoint|/path/to/your/ca-cert\.pem|azure/your-|azure/your-deployment-name' "$CONFIG_FILE" >/dev/null; then
        echo -e "${RED}错误: $CONFIG_FILE 中仍存在占位配置，请先替换为真实值：${NC}"
        grep -nE 'your-azure-api-endpoint|/path/to/your/ca-cert\.pem|azure/your-|azure/your-deployment-name' "$CONFIG_FILE" || true
        exit 1
    fi

    if [ "$USE_AZURE" = "1" ]; then
        require_env AZURE_CLIENT_ID
        require_env AZURE_CLIENT_SECRET
        require_env AZURE_TENANT_ID
    fi

    if [ "$USE_VERTEX" = "1" ]; then
        require_env VERTEX_PROJECT
        require_env VERTEX_LOCATION
        if [ -n "${GOOGLE_APPLICATION_CREDENTIALS:-}" ]; then
            if is_placeholder "$GOOGLE_APPLICATION_CREDENTIALS"; then
                die "错误: GOOGLE_APPLICATION_CREDENTIALS 仍为占位值，请在 $ENV_FILE 中填写真实路径"
            fi
            if [ ! -f "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
                die "错误: GOOGLE_APPLICATION_CREDENTIALS 文件不存在 -> $GOOGLE_APPLICATION_CREDENTIALS"
            fi
        else
            warn "提示: 未设置 GOOGLE_APPLICATION_CREDENTIALS，请确保已完成 gcloud ADC 登录"
        fi
    fi

    if [ "$USE_DASHSCOPE" = "1" ]; then
        require_env DASHSCOPE_API_KEY
    fi

    if [ -n "${SSL_CERT_FILE:-}" ] && grep -qE '/path/to/your/ca-cert\.pem' "$CONFIG_FILE"; then
        warn "提示: 已设置 SSL_CERT_FILE，但 $CONFIG_FILE 的 ssl_verify 仍为占位路径，请同步更新为真实证书路径"
    fi
fi

# 5. 检查依赖项
PYTHON_BIN="${PYTHON_BIN:-}"
if [ -z "$PYTHON_BIN" ]; then
    if command -v python3 &> /dev/null; then
        PYTHON_BIN="python3"
    else
        PYTHON_BIN="python"
    fi
fi

if ! "$PYTHON_BIN" -m pip --version &> /dev/null; then
    die "错误: 未找到 pip，请先为 $PYTHON_BIN 安装 pip"
fi

if ! command -v litellm &> /dev/null; then
    echo -e "${YELLOW}正在安装必要依赖 (litellm, azure-identity, google-generativeai)...${NC}"
    "$PYTHON_BIN" -m pip install -U 'litellm[proxy]' azure-identity google-generativeai
fi

# 6. 启动服务
echo -e "${GREEN}一切就绪，正在启动 LiteLLM Proxy...${NC}"
HOST="${LITELLM_HOST:-0.0.0.0}"
PORT="${LITELLM_PORT:-4000}"
echo -e "${YELLOW}代理地址: http://$HOST:$PORT${NC}"

MASTER_KEY="${LITELLM_MASTER_KEY:-}"
if [ -z "$MASTER_KEY" ]; then
    echo -e "${YELLOW}Master Key: 未设置${NC}"
else
    if [ "${#MASTER_KEY}" -lt 9 ]; then
        MASKED_MASTER_KEY="****"
    else
        MASKED_MASTER_KEY="${MASTER_KEY:0:4}****${MASTER_KEY: -4}"
    fi
    echo -e "${YELLOW}Master Key: $MASKED_MASTER_KEY${NC}"
fi

if [ "${LITELLM_MASTER_KEY:-}" = "sk-1234" ]; then
    echo -e "${YELLOW}警告: LITELLM_MASTER_KEY 仍为默认值 sk-1234，建议立即修改。${NC}"
fi

if command -v lsof &> /dev/null; then
    LISTEN_PID="$(lsof -nP -iTCP:"$PORT" -sTCP:LISTEN -t 2>/dev/null || true)"
    if [ -n "$LISTEN_PID" ]; then
        die "错误: 端口 $PORT 已被占用 (PID: $LISTEN_PID)。请修改 LITELLM_PORT 或停止占用进程。"
    fi
fi

if [ "$DRY_RUN" = "1" ]; then
    info "dry-run 模式：配置检查完成，未启动服务。"
    exit 0
fi

# 启动 litellm
litellm --config "$CONFIG_FILE" --host "$HOST" --port "$PORT"
