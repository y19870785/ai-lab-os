"""Prepare and clean a temporary Hermes project for the internal P1A pilot."""

from __future__ import annotations

import argparse
import shutil
import tempfile
from pathlib import Path

import yaml

EXPECTED_MODEL_TOOL_SUFFIXES = (
    "ai_lab_interaction_preview",
    "ai_lab_interaction_status",
    "ai_lab_interaction_view",
    "ai_lab_interaction_confirm",
)
FORBIDDEN_MODEL_TOOL_TOKENS = (
    "terminal", "process", "shell", "powershell", "python", "computer",
    "browser", "write_file", "patch", "install", "execute", "verify",
    "recover", "approve", "tool_search", "tool_call", "tool_describe",
)


def build_gateway_command(hermes_python: str) -> list[str]:
    """Start the temporary gateway without touching the installed service unit."""

    executable = hermes_python.strip()
    if not executable:
        raise ValueError("Hermes Python executable is required")
    # `hermes gateway run` refreshes the installed systemd unit on startup.
    # A temporary HERMES_HOME must bypass that CLI self-heal path.
    return [executable, "-m", "gateway.run"]


def enforce_model_tool_profile(tool_names: list[str]) -> None:
    """Fail closed unless the Hermes-visible namespace is exactly four tools."""

    suffixes = tuple(name.rsplit("__", 1)[-1] for name in tool_names)
    if set(suffixes) != set(EXPECTED_MODEL_TOOL_SUFFIXES) or len(tool_names) != 4:
        raise RuntimeError("INTERNAL_PILOT_TOOL_ISOLATION_UNPROVEN")
    lowered = [name.casefold() for name in tool_names]
    if any(token in name for token in FORBIDDEN_MODEL_TOOL_TOKENS for name in lowered):
        raise RuntimeError("INTERNAL_PILOT_TOOL_ISOLATION_UNPROVEN")


def prepare_temporary_project(
    *, source_hermes_home: Path, mcp_command: list[str], root: Path | None = None,
) -> Path:
    """Project the plugin and a narrowed config without touching live discovery."""

    project = root or Path(tempfile.mkdtemp(prefix="ai-lab-pilot-001-p1a-"))
    project.mkdir(parents=True, exist_ok=True)
    hermes_home = project / ".hermes-home"
    hermes_home.mkdir(mode=0o700)
    source_config = source_hermes_home / "config.yaml"
    config = yaml.safe_load(source_config.read_text(encoding="utf-8")) or {}
    for platform_name, platform_config in (config.get("platforms") or {}).items():
        if isinstance(platform_config, dict):
            platform_config["enabled"] = platform_name == "wecom"
    # Project plugins are opt-in.  This key matches the required nested
    # projection path (<project>/.hermes/plugins/platforms/wecom), allowing
    # its concrete adapter registration to replace Hermes' deferred bundled
    # WeCom registration for this temporary project only.
    config["plugins"] = {"enabled": ["platforms/wecom"]}
    config["platform_toolsets"] = {"wecom": ["ai-lab-p1a"]}
    config.setdefault("tools", {})["tool_search"] = {"enabled": "off"}
    config["mcp_servers"] = {
        "ai-lab-p1a": {
            "command": mcp_command[0],
            "args": mcp_command[1:],
            "enabled": True,
            "tools": {
                "include": list(EXPECTED_MODEL_TOOL_SUFFIXES),
                "resources": False,
                "prompts": False,
            },
        }
    }
    (hermes_home / "config.yaml").write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    for name in ("auth.json",):
        source = source_hermes_home / name
        if source.is_file():
            shutil.copy2(source, hermes_home / name)
    source_env = source_hermes_home / ".env"
    if source_env.is_file():
        blocked_platform_prefixes = (
            "TELEGRAM_", "DISCORD_", "SLACK_", "WHATSAPP_", "WEIXIN_",
            "FEISHU_", "LINE_", "SIGNAL_", "MATRIX_",
        )
        retained = []
        for line in source_env.read_text(encoding="utf-8").splitlines():
            key = line.split("=", 1)[0].strip() if "=" in line else ""
            if not any(key.startswith(prefix) for prefix in blocked_platform_prefixes):
                retained.append(line)
        (hermes_home / ".env").write_text("\n".join(retained) + "\n", encoding="utf-8")
    template = Path(__file__).parent / "plugin_template" / "platforms" / "wecom"
    destination = project / ".hermes" / "plugins" / "platforms" / "wecom"
    shutil.copytree(template, destination)
    return project


def cleanup_temporary_project(project: Path) -> None:
    """Remove only a launcher-created, positively identified temporary root."""

    resolved = project.resolve()
    if not resolved.name.startswith("ai-lab-pilot-001-p1a-"):
        raise RuntimeError("refusing to remove an unrecognized project root")
    shutil.rmtree(resolved)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("verify-tools",))
    parser.add_argument("tools", nargs="*")
    args = parser.parse_args()
    enforce_model_tool_profile(args.tools)
    print("INTERNAL_PILOT_TOOL_ALLOWLIST_EXACT")


if __name__ == "__main__":
    main()
