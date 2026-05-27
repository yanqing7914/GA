from __future__ import annotations

import argparse
import sys

from .config import McpConfig
from .server import build_server


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GenericAgent MCP Server")
    parser.add_argument("--transport", choices=["stdio", "sse", "streamable-http"], default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5050)
    parser.add_argument("--log-level", default="info")
    parser.add_argument(
        "--auth-mode",
        choices=["static", "oauth"],
        default="static",
        help="HTTP auth mode. static accepts GA_MCP_TOKEN as a direct Bearer token; oauth uses MCP SDK resource metadata.",
    )
    parser.add_argument(
        "--allow-unauthenticated-local",
        action="store_true",
        help="Allow unauthenticated HTTP only for explicit local debugging.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if args.transport != "stdio" and args.host == "0.0.0.0":
        raise SystemExit("Refusing to listen on 0.0.0.0; use 127.0.0.1 behind a named tunnel")

    config = McpConfig.from_env()
    require_auth = args.transport != "stdio" and not args.allow_unauthenticated_local
    if require_auth and not config.token:
        raise SystemExit("GA_MCP_TOKEN is required for HTTP/SSE transport")

    mcp = build_server(
        config,
        args.transport,
        require_auth=require_auth,
        host=args.host,
        port=args.port,
        auth_mode=args.auth_mode,
    )
    try:
        mcp.run(transport=args.transport)
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
