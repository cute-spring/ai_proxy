# LiteLLM Proxy 企业级多模型网关配置指南

本项目旨在为本地开发环境提供一个统一的 LLM 代理网关，集成 **Azure OpenAI (Service Principal 认证)**、**Google Vertex AI (个人账户认证)** 以及 **通义千问 Qwen (DashScope API)**，并针对企业内网 SSL 检查环境进行了优化。

## 30 秒成功（只看这一段）

1) 一键向导（自动创建 venv、安装依赖、生成配置、校验、可选安装开机自启）：
```bash
chmod +x scripts/bootstrap_cli.sh
./scripts/bootstrap_cli.sh
```

2) 启动服务：
```bash
chmod +x start_proxy.sh
./start_proxy.sh
```

3) 健康检查（返回 ok/ready 即成功）：
```bash
curl http://localhost:4000/health/readiness
```

企业内网常见要求：
- 需要公司 CA：准备 PEM 格式证书路径（向导会询问 `SSL_CERT_FILE`）
- 需要走代理：准备出口代理地址（向导会询问 `AZURE_PROXY` / `GEMINI_PROXY` / `QWEN_PROXY`）

## 0. 快速上手（零上下文）

如果你只想“马上跑起来”，推荐使用交互式向导（自动生成 `.env` / `config.yaml`，做校验，并可选安装开机自启）：

```bash
./scripts/bootstrap_cli.sh
```

完成后：
- 启动服务：`./start_proxy.sh`
- 健康检查：`curl http://localhost:4000/health/readiness`

---

## 1. 核心功能
- **统一入口**：通过 OpenAI 兼容的 API 格式访问 Azure、Google 和 Qwen 模型。
- **证书优化**：自动加载自定义 CA 证书，解决企业网络下的 SSL 校验失败问题。
- **分模型代理**：支持为不同云服务商配置独立的 HTTP/HTTPS 出口代理。
- **自动认证**：支持 Azure Token Provider 模式和 Google ADC 模式。
- **安全保护**：内置 Master Key 认证，防止代理被非法调用。

---

## 2. 环境准备

在开始之前，请确保您的机器已安装以下工具：
1. **Python 3.9+**
2. **Azure CLI** (`az login`)
3. **Google Cloud SDK** (`gcloud auth application-default login`)

---

## 3. 安装与配置

### 第一步：配置环境变量
编辑项目根目录下的 [.env](file:///Users/gavinzhang/Documents/trae_projects/ai_proxy/.env) 文件，填写您的凭据：

```bash
# --- 服务监听 ---
LITELLM_HOST=0.0.0.0
LITELLM_PORT=4000

# --- Azure 认证 (Service Principal) ---
AZURE_CLIENT_ID=您的客户端ID
AZURE_CLIENT_SECRET=您的客户端密钥
AZURE_TENANT_ID=您的租户ID

# --- Google Cloud (Vertex AI) 配置 ---
VERTEX_PROJECT=您的GCP项目ID
VERTEX_LOCATION=us-central1 # 或其他区域
GOOGLE_APPLICATION_CREDENTIALS=/Users/您的用户名/path/to/service-account.json # 可留空，改用 gcloud ADC

# --- Alibaba Cloud (DashScope) 配置 ---
DASHSCOPE_API_KEY=您的DashScope_API_KEY

# --- 分模型出口代理 (按需填写) ---
AZURE_PROXY=http://azure-proxy-server:8080
GEMINI_PROXY=http://gemini-proxy-server:8080
QWEN_PROXY=http://qwen-proxy-server:8080
NO_PROXY=localhost,127.0.0.1,0.0.0.0

# --- 企业 CA 证书 ---
SSL_CERT_FILE=/Users/您的用户名/path/to/ca-cert.pem

# --- 代理安全 ---
LITELLM_MASTER_KEY=sk-1234 # 强烈建议修改此默认 Key
```

### 第二步：更新模型路由配置
编辑 [config.yaml](file:///Users/gavinzhang/Documents/trae_projects/ai_proxy/config.yaml)，更新您的资源部署名称：

```yaml
  - model_name: gpt-4
    litellm_params:
      model: azure/您的部署名
      api_base: https://您的资源名.openai.azure.com/
      # 其他参数如 api_version, http_proxy 已预设
```

### 模型与别名（你在请求里写的 model 字段）

| model | 上游 | 说明 |
| :--- | :--- | :--- |
| `gpt-4` / `gpt-4.1` / `gpt-4.1-mini` / `gpt-5` / `gpt-5-mini` / `gpt-5-nano` | Azure OpenAI | 这些是代理侧别名；需要你在 Azure 创建对应 deployment 并填到 `azure/<deployment>` |
| `gemini-pro` | Vertex AI | 映射到 `vertex_ai/gemini-1.5-pro` |
| `gemini-3-flash` | Vertex AI | 映射到 `vertex_ai/gemini-3-flash` |
| `gemini-3-pro` | Vertex AI | 映射到 `vertex_ai/gemini-3-pro` |
| `qwen-max` | DashScope | 映射到 `dashscope/qwen-max` |

### 第三步：云平台认证 (针对企业级 Vertex AI)
根据您的企业安全要求，选择以下一种方式：
- **方式 A (个人账户)**: 在终端运行 `gcloud auth application-default login`。
- **方式 B (服务账号)**: 获取 JSON 密钥文件，并在 `.env` 中设置 `GOOGLE_APPLICATION_CREDENTIALS` 指向该文件。这在企业自动化部署中更常用。

---

## 4. 启动与验证

### 启动服务
在终端执行：
```bash
chmod +x start_proxy.sh
./start_proxy.sh
```

### 健康检查
服务启动后，可以通过以下命令验证状态：
```bash
curl http://localhost:4000/health/readiness
```

---

## 4.1 交互式安装向导（推荐）

如果你希望“不看文档也能配置完成”，可以使用交互式向导。它会引导你填写配置、自动生成 `.env` / `config.yaml`、执行校验，并可选安装为 macOS 开机自启服务（launchd）。

### 方式 A：一键创建 venv + 安装依赖 + 运行向导（推荐）
```bash
chmod +x scripts/bootstrap_cli.sh
./scripts/bootstrap_cli.sh
```

### 方式 B：已安装 click/rich 时使用（自动 fallback）
```bash
chmod +x scripts/setup
./scripts/setup
```

### 方式 C：bash 向导（零 Python 依赖）
```bash
chmod +x scripts/setup_wizard.sh
./scripts/setup_wizard.sh
```

### Python CLI 常用命令
```bash
python3 -m pip install -r requirements-cli.txt
python3 scripts/ai_proxy_cli.py wizard
python3 scripts/ai_proxy_cli.py validate
python3 scripts/ai_proxy_cli.py launchd install
python3 scripts/ai_proxy_cli.py start
```

## 5. 调用示例

#### Python (OpenAI SDK)
```python
import os
from openai import OpenAI

client = OpenAI(api_key=os.environ["LITELLM_MASTER_KEY"], base_url="http://localhost:4000")

# 调用 Azure GPT-5 mini（示例）
response = client.chat.completions.create(
    model="gpt-5-mini",
    messages=[{"role": "user", "content": "你好"}]
)
print(response.choices[0].message.content)
```

#### Node.js (OpenAI SDK)
```javascript
const OpenAI = require('openai');
const openai = new OpenAI({
  apiKey: process.env.LITELLM_MASTER_KEY,
  baseURL: 'http://localhost:4000/v1'
});

async function main() {
  const completion = await openai.chat.completions.create({
    messages: [{ role: 'user', content: '介绍一下 Gemini' }],
    model: 'gemini-3-pro',
  });
  console.log(completion.choices[0].message.content);
}
main();
```

---

## 6. 进阶配置说明 (config.yaml)

- **`drop_params: True`**: 自动过滤掉不同模型间不兼容的 OpenAI 参数（如 Azure 不支持 `top_k`），防止调用报错。
- **`rpm: 1000`**: 设置每分钟请求频率限制，保护上游 API 不被封禁。
- **`ssl_verify`**: 显式指定证书路径，确保在复杂的公司网络环境下请求安全。

---

## 7. 常见问题 (FAQ)

| 问题 | 解决方法 |
| :--- | :--- |
| **SSL 证书校验失败** | 确保 `.env` 中的 `SSL_CERT_FILE` 是 PEM 格式的绝对路径。 |
| **Azure 401 错误** | 检查 Service Principal 是否拥有 `Cognitive Services OpenAI User` 权限。 |
| **Gemini 403 错误** | 运行 `gcloud auth application-default login` 并确保项目已开启 Vertex AI API。 |
| **模型找不到** | 检查调用时的 `model` 字符串是否与 `config.yaml` 中的 `model_name` 完全一致。 |
| **端口被占用** | 设置 `.env` 中 `LITELLM_PORT` 为其他端口，或停止占用该端口的进程。 |
| **企业代理不同模型不同出口** | 在 `.env` 填写 `AZURE_PROXY` / `GEMINI_PROXY` / `QWEN_PROXY`，并确认 `NO_PROXY` 包含 `localhost,127.0.0.1`。 |
| **Vertex AI 企业认证失败** | 优先使用 `GOOGLE_APPLICATION_CREDENTIALS`（服务账号 JSON），并确保文件路径可读。 |

---

## 8. 项目维护
- **添加新模型**：在 `config.yaml` 的 `model_list` 下新增条目，并在 `.env` 中添加相应的环境变量。
- **查看日志**：LiteLLM 默认输出到终端。如需保存日志，建议使用 `nohup ./start_proxy.sh > proxy.log 2>&1 &`。

---

## 9. 多协议支持 (Anthropic 兼容)

LiteLLM Proxy 除了支持 OpenAI 格式外，还支持 **Anthropic 风格** 的调用。您可以直接使用 Anthropic SDK 连接代理：

### Python (Anthropic SDK)
```python
from anthropic import Anthropic

client = Anthropic(
    api_key="sk-1234", 
    base_url="http://localhost:4000"
)

# 代理会自动将 Anthropic 格式转换为后端模型所需的格式
response = client.messages.create(
    model="gpt-4",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello via Anthropic SDK"}]
)
```

---

## 10. macOS 自动启动 (launchd)

如果您不希望每次都手工运行 `./start_proxy.sh`，推荐使用 macOS 原生的 **launchd**（LaunchAgent）让服务在“用户登录后自动启动”，并在异常退出时自动拉起。

### 方案 A：使用模板脚本一键安装（推荐）

项目已提供模板与安装脚本：
- 模板 plist：[com.local.litellm.proxy.plist.template](file:///Users/gavinzhang/Documents/trae_projects/ai_proxy/scripts/launchd/com.local.litellm.proxy.plist.template)
- 安装脚本：[install.sh](file:///Users/gavinzhang/Documents/trae_projects/ai_proxy/scripts/launchd/install.sh)
- 卸载脚本：[uninstall.sh](file:///Users/gavinzhang/Documents/trae_projects/ai_proxy/scripts/launchd/uninstall.sh)
- 状态查看：[status.sh](file:///Users/gavinzhang/Documents/trae_projects/ai_proxy/scripts/launchd/status.sh)

1) 赋予脚本可执行权限：
```bash
chmod +x scripts/launchd/*.sh
```

2) 安装并启动（默认 label 为 `com.local.litellm.proxy`）：
```bash
./scripts/launchd/install.sh
```

3) 查看运行状态：
```bash
./scripts/launchd/status.sh
```

4) 卸载（停止并移除 LaunchAgent）：
```bash
./scripts/launchd/uninstall.sh
```

可选：自定义 label 与项目路径：
```bash
LABEL=com.yourcompany.litellm.proxy PROJECT_DIR=/absolute/path/to/ai_proxy ./scripts/launchd/install.sh
```

日志默认写入：
- `./logs/launchd/stdout.log`
- `./logs/launchd/stderr.log`

### 方案 B：手工创建 LaunchAgent（理解 launchd 机制）

1) 将模板生成后的 plist 放到：
`~/Library/LaunchAgents/com.local.litellm.proxy.plist`

2) 加载并启用开机自启：
```bash
launchctl load -w ~/Library/LaunchAgents/com.local.litellm.proxy.plist
```

3) 手工启动/停止：
```bash
launchctl start com.local.litellm.proxy
launchctl stop com.local.litellm.proxy
```

4) 卸载：
```bash
launchctl unload -w ~/Library/LaunchAgents/com.local.litellm.proxy.plist
```

### 运行注意事项（企业内网常见）

- **PATH 问题**：LaunchAgent 的 PATH 与终端不同，模板已预置 `/opt/homebrew/bin`、`/usr/local/bin` 等常见路径。
- **认证方式**：Vertex AI 推荐使用 `.env` 中的 `GOOGLE_APPLICATION_CREDENTIALS`（服务账号 JSON），更适合长期运行；否则需提前完成 `gcloud auth application-default login`。
- **代理与证书**：服务会从 `.env` 加载 `SSL_CERT_FILE` 与分模型代理变量，并在启动前做占位符校验，避免启动后才报错。
