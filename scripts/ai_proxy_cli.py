#!/usr/bin/env python3

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    import click
except Exception as e:
    print(f"Missing dependency: click ({e}).", file=sys.stderr)
    sys.exit(1)

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
except Exception:
    print("Missing dependency: rich. Install with: python3 -m pip install -r requirements-cli.txt", file=sys.stderr)
    sys.exit(1)


console = Console()


@dataclass(frozen=True)
class WizardPaths:
    root_dir: Path
    env_file: Path
    config_file: Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def format_env_value(value: str) -> str:
    if value == "":
        return '""'
    if re.search(r"""[\s#'"\\]""", value):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def write_env_file(env_path: Path, kvs: dict[str, str]) -> None:
    lines: list[str] = []
    for k, v in kvs.items():
        lines.append(f"{k}={format_env_value(v)}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_cmd(cmd: list[str], cwd: Path, env: Optional[dict[str, str]] = None) -> int:
    p = subprocess.Popen(cmd, cwd=str(cwd), env=env or os.environ.copy())
    return p.wait()


def file_must_exist(label: str, path_str: str) -> None:
    if not path_str:
        return
    p = Path(path_str).expanduser()
    if not p.exists():
        raise click.ClickException(f"{label} file not found: {p}")


def normalize_endpoint(endpoint: str) -> str:
    endpoint = endpoint.strip()
    if endpoint and not endpoint.endswith("/"):
        endpoint += "/"
    return endpoint


def build_config_yaml(
    *,
    ssl_cert_file: str,
    azure_enabled: bool,
    azure_api_base: str,
    azure_api_version: str,
    azure_models: dict[str, str],
    azure_use_proxy: bool,
    vertex_enabled: bool,
    vertex_models: list[str],
    vertex_use_proxy: bool,
    qwen_enabled: bool,
    qwen_use_proxy: bool,
    master_key: str,
) -> str:
    def line(s: str) -> str:
        return s

    def maybe_ssl(lines: list[str]) -> None:
        if ssl_cert_file:
            lines.append(line(f'      ssl_verify: "{ssl_cert_file}"'))

    lines: list[str] = []
    lines.append("model_list:")

    if azure_enabled:
        for model_name, deployment in azure_models.items():
            if not deployment:
                continue
            lines.extend(
                [
                    line(f"  - model_name: {model_name}"),
                    line("    litellm_params:"),
                    line(f"      model: azure/{deployment}"),
                    line(f"      api_base: {azure_api_base}"),
                    line(f'      api_version: "{azure_api_version}"'),
                    line("      use_azure_ad: True"),
                ]
            )
            maybe_ssl(lines)
            if azure_use_proxy:
                lines.append(line('      http_proxy: "os.environ/AZURE_PROXY"'))
            lines.append(line("      rpm: 1000"))
            lines.append("")

    if vertex_enabled:
        for model_name, model_id in [
            ("gemini-pro", "gemini-1.5-pro"),
            ("gemini-3-flash", "gemini-3-flash"),
            ("gemini-3-pro", "gemini-3-pro"),
        ]:
            if model_name not in vertex_models:
                continue
            lines.extend(
                [
                    line(f"  - model_name: {model_name}"),
                    line("    litellm_params:"),
                    line(f"      model: vertex_ai/{model_id}"),
                    line('      vertex_project: "os.environ/VERTEX_PROJECT"'),
                    line('      vertex_location: "os.environ/VERTEX_LOCATION"'),
                ]
            )
            if vertex_use_proxy:
                lines.append(line('      http_proxy: "os.environ/GEMINI_PROXY"'))
            maybe_ssl(lines)
            lines.append("")

    if qwen_enabled:
        lines.extend(
            [
                line("  - model_name: qwen-max"),
                line("    litellm_params:"),
                line("      model: dashscope/qwen-max"),
                line('      api_key: "os.environ/DASHSCOPE_API_KEY"'),
            ]
        )
        if qwen_use_proxy:
            lines.append(line('      http_proxy: "os.environ/QWEN_PROXY"'))
        maybe_ssl(lines)
        lines.append("")

    lines.extend(
        [
            "router_settings:",
            "  routing_strategy: simple-shuffle",
            "  model_group_alias:",
            '    "default-model": []',
            "",
            "general_settings:",
            f"  master_key: {master_key}",
            "",
            "litellm_settings:",
            "  drop_params: True",
            "  set_verbose: False",
            "",
        ]
    )
    return "\n".join(lines)


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
def cli() -> None:
    pass


@cli.command("wizard")
@click.option("--env-file", type=click.Path(path_type=Path), default=None)
@click.option("--config-file", type=click.Path(path_type=Path), default=None)
@click.option("--project-dir", type=click.Path(path_type=Path), default=None)
def wizard(env_file: Optional[Path], config_file: Optional[Path], project_dir: Optional[Path]) -> None:
    root = (project_dir or project_root()).resolve()
    paths = WizardPaths(
        root_dir=root,
        env_file=(env_file or (root / ".env")).resolve(),
        config_file=(config_file or (root / "config.yaml")).resolve(),
    )

    console.print(Panel.fit(f"Project: {paths.root_dir}", title="LiteLLM Proxy Setup Wizard"))

    host = click.prompt("LiteLLM host", default=os.environ.get("LITELLM_HOST", "0.0.0.0"))
    port = click.prompt("LiteLLM port", default=os.environ.get("LITELLM_PORT", "4000"))

    ssl_cert_file = click.prompt("CA cert path (optional)", default=os.environ.get("SSL_CERT_FILE", ""), show_default=False)
    file_must_exist("CA cert", ssl_cert_file)

    master_key = click.prompt(
        "Master key (blank to generate)",
        default=os.environ.get("LITELLM_MASTER_KEY", ""),
        show_default=False,
    )
    if not master_key:
        master_key = subprocess.check_output([sys.executable, "-c", "import secrets;print('sk-'+secrets.token_urlsafe(24))"]).decode().strip()
        console.print("[green]Generated master key and will write to .env[/green]")

    azure_enabled = click.confirm("Enable Azure OpenAI?", default=True)
    vertex_enabled = click.confirm("Enable Vertex AI Gemini?", default=True)
    qwen_enabled = click.confirm("Enable Qwen (DashScope)?", default=False)

    kvs: dict[str, str] = {
        "LITELLM_HOST": str(host),
        "LITELLM_PORT": str(port),
        "SSL_CERT_FILE": ssl_cert_file,
        "LITELLM_MASTER_KEY": master_key,
        "NO_PROXY": os.environ.get("NO_PROXY", "localhost,127.0.0.1,0.0.0.0"),
    }

    azure_api_base = ""
    azure_api_version = "2024-02-15-preview"
    azure_models: dict[str, str] = {}
    azure_use_proxy = False
    if azure_enabled:
        kvs["AZURE_CLIENT_ID"] = click.prompt("AZURE_CLIENT_ID")
        kvs["AZURE_CLIENT_SECRET"] = click.prompt("AZURE_CLIENT_SECRET", hide_input=True)
        kvs["AZURE_TENANT_ID"] = click.prompt("AZURE_TENANT_ID")
        azure_api_base = normalize_endpoint(click.prompt("Azure api_base (https://xxx.openai.azure.com/)"))
        azure_api_version = click.prompt("Azure api_version", default=azure_api_version)
        kvs["AZURE_PROXY"] = click.prompt("AZURE_PROXY (optional)", default=os.environ.get("AZURE_PROXY", ""), show_default=False)
        azure_use_proxy = bool(kvs["AZURE_PROXY"])

        console.print(Panel.fit("Enter Azure deployment names (blank = skip)", title="Azure Deployments"))
        azure_models = {
            "gpt-4": click.prompt("Deployment for gpt-4", default="", show_default=False),
            "gpt-4.1": click.prompt("Deployment for gpt-4.1", default="", show_default=False),
            "gpt-4.1-mini": click.prompt("Deployment for gpt-4.1-mini", default="", show_default=False),
            "gpt-5": click.prompt("Deployment for gpt-5", default="", show_default=False),
            "gpt-5-mini": click.prompt("Deployment for gpt-5-mini", default="", show_default=False),
            "gpt-5-nano": click.prompt("Deployment for gpt-5-nano", default="", show_default=False),
        }

    vertex_models: list[str] = []
    vertex_use_proxy = False
    if vertex_enabled:
        kvs["VERTEX_PROJECT"] = click.prompt("VERTEX_PROJECT", default=os.environ.get("VERTEX_PROJECT", ""))
        kvs["VERTEX_LOCATION"] = click.prompt("VERTEX_LOCATION", default=os.environ.get("VERTEX_LOCATION", "us-central1"))
        kvs["GEMINI_PROXY"] = click.prompt("GEMINI_PROXY (optional)", default=os.environ.get("GEMINI_PROXY", ""), show_default=False)
        vertex_use_proxy = bool(kvs["GEMINI_PROXY"])
        kvs["GOOGLE_APPLICATION_CREDENTIALS"] = click.prompt(
            "GOOGLE_APPLICATION_CREDENTIALS (optional, service account json path)",
            default=os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", ""),
            show_default=False,
        )
        file_must_exist("Service account json", kvs["GOOGLE_APPLICATION_CREDENTIALS"])

        vertex_models = []
        if click.confirm("Add gemini-1.5-pro (alias: gemini-pro)?", default=True):
            vertex_models.append("gemini-pro")
        if click.confirm("Add gemini-3-flash?", default=True):
            vertex_models.append("gemini-3-flash")
        if click.confirm("Add gemini-3-pro?", default=True):
            vertex_models.append("gemini-3-pro")

    qwen_use_proxy = False
    if qwen_enabled:
        kvs["DASHSCOPE_API_KEY"] = click.prompt("DASHSCOPE_API_KEY", hide_input=True)
        kvs["QWEN_PROXY"] = click.prompt("QWEN_PROXY (optional)", default=os.environ.get("QWEN_PROXY", ""), show_default=False)
        qwen_use_proxy = bool(kvs["QWEN_PROXY"])

    write_env_file(paths.env_file, kvs)

    config_yaml = build_config_yaml(
        ssl_cert_file=ssl_cert_file,
        azure_enabled=azure_enabled,
        azure_api_base=azure_api_base,
        azure_api_version=azure_api_version,
        azure_models=azure_models,
        azure_use_proxy=azure_use_proxy,
        vertex_enabled=vertex_enabled,
        vertex_models=vertex_models,
        vertex_use_proxy=vertex_use_proxy,
        qwen_enabled=qwen_enabled,
        qwen_use_proxy=qwen_use_proxy,
        master_key=master_key,
    )
    paths.config_file.write_text(config_yaml, encoding="utf-8")

    table = Table(title="Generated Files")
    table.add_column("File")
    table.add_column("Path")
    table.add_row(".env", str(paths.env_file))
    table.add_row("config.yaml", str(paths.config_file))
    console.print(table)

    console.print(Panel.fit("Validating configuration (dry-run)...", title="Validate"))
    code = validate_impl(paths)
    if code != 0:
        raise click.ClickException("Validation failed. Fix errors and re-run.")

    if click.confirm("Install launchd auto-start on this Mac?", default=True):
        label = click.prompt("launchd label", default="com.local.litellm.proxy")
        install_launchd_impl(paths, label=label)

    if click.confirm("Start service now (foreground)?", default=False):
        start_impl(paths)
    else:
        console.print("[green]Done.[/green] You can start later with: ./start_proxy.sh")


def validate_impl(paths: WizardPaths) -> int:
    env = os.environ.copy()
    env["ENV_FILE"] = str(paths.env_file)
    env["CONFIG_FILE"] = str(paths.config_file)
    cmd = [str(paths.root_dir / "start_proxy.sh"), "--dry-run"]
    return run_cmd(cmd, cwd=paths.root_dir, env=env)


def start_impl(paths: WizardPaths) -> int:
    env = os.environ.copy()
    env["ENV_FILE"] = str(paths.env_file)
    env["CONFIG_FILE"] = str(paths.config_file)
    cmd = [str(paths.root_dir / "start_proxy.sh")]
    return run_cmd(cmd, cwd=paths.root_dir, env=env)


def install_launchd_impl(paths: WizardPaths, *, label: str) -> None:
    cmd = [str(paths.root_dir / "scripts" / "launchd" / "install.sh")]
    env = os.environ.copy()
    env["LABEL"] = label
    env["PROJECT_DIR"] = str(paths.root_dir)
    code = run_cmd(cmd, cwd=paths.root_dir, env=env)
    if code != 0:
        raise click.ClickException("launchd install failed")


def uninstall_launchd_impl(paths: WizardPaths, *, label: str) -> None:
    cmd = [str(paths.root_dir / "scripts" / "launchd" / "uninstall.sh")]
    env = os.environ.copy()
    env["LABEL"] = label
    code = run_cmd(cmd, cwd=paths.root_dir, env=env)
    if code != 0:
        raise click.ClickException("launchd uninstall failed")


@cli.command("validate")
@click.option("--env-file", type=click.Path(path_type=Path), default=None)
@click.option("--config-file", type=click.Path(path_type=Path), default=None)
@click.option("--project-dir", type=click.Path(path_type=Path), default=None)
def validate_cmd(env_file: Optional[Path], config_file: Optional[Path], project_dir: Optional[Path]) -> None:
    root = (project_dir or project_root()).resolve()
    paths = WizardPaths(root, (env_file or (root / ".env")).resolve(), (config_file or (root / "config.yaml")).resolve())
    code = validate_impl(paths)
    raise SystemExit(code)


@cli.group("launchd")
def launchd_group() -> None:
    pass


@launchd_group.command("install")
@click.option("--label", default="com.local.litellm.proxy")
@click.option("--project-dir", type=click.Path(path_type=Path), default=None)
def launchd_install(label: str, project_dir: Optional[Path]) -> None:
    root = (project_dir or project_root()).resolve()
    paths = WizardPaths(root, (root / ".env").resolve(), (root / "config.yaml").resolve())
    install_launchd_impl(paths, label=label)


@launchd_group.command("uninstall")
@click.option("--label", default="com.local.litellm.proxy")
@click.option("--project-dir", type=click.Path(path_type=Path), default=None)
def launchd_uninstall(label: str, project_dir: Optional[Path]) -> None:
    root = (project_dir or project_root()).resolve()
    paths = WizardPaths(root, (root / ".env").resolve(), (root / "config.yaml").resolve())
    uninstall_launchd_impl(paths, label=label)


@launchd_group.command("status")
@click.option("--label", default="com.local.litellm.proxy")
@click.option("--project-dir", type=click.Path(path_type=Path), default=None)
def launchd_status(label: str, project_dir: Optional[Path]) -> None:
    root = (project_dir or project_root()).resolve()
    cmd = [str(root / "scripts" / "launchd" / "status.sh")]
    env = os.environ.copy()
    env["LABEL"] = label
    raise SystemExit(run_cmd(cmd, cwd=root, env=env))


@cli.command("start")
@click.option("--env-file", type=click.Path(path_type=Path), default=None)
@click.option("--config-file", type=click.Path(path_type=Path), default=None)
@click.option("--project-dir", type=click.Path(path_type=Path), default=None)
def start_cmd(env_file: Optional[Path], config_file: Optional[Path], project_dir: Optional[Path]) -> None:
    root = (project_dir or project_root()).resolve()
    paths = WizardPaths(root, (env_file or (root / ".env")).resolve(), (config_file or (root / "config.yaml")).resolve())
    raise SystemExit(start_impl(paths))


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
