"""Hermes-native model tool resolver used as the mandatory startup gate."""

from __future__ import annotations

import json


def main() -> None:
    from hermes_cli.config import load_config_readonly
    from hermes_cli.tools_config import _get_platform_tools
    from model_tools import get_tool_definitions
    from tools.mcp_tool import discover_mcp_tools, shutdown_mcp_servers

    config = load_config_readonly()
    try:
        discover_mcp_tools()
        enabled = sorted(_get_platform_tools(config, "wecom"))
        disabled = (config.get("agent") or {}).get("disabled_toolsets") or None
        definitions = get_tool_definitions(
            enabled_toolsets=enabled,
            disabled_toolsets=disabled,
            quiet_mode=True,
        )
        names = [item["function"]["name"] for item in definitions]
        print(json.dumps(names, separators=(",", ":")))
    finally:
        shutdown_mcp_servers()


if __name__ == "__main__":
    main()
