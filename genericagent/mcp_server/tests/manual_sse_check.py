"""Manual SSE smoke test for a running GenericAgent MCP server.

Usage:
  set GA_MCP_TOKEN=replace-with-secret
  python ga_mcp_server.py --transport sse --host 127.0.0.1 --port 5050
  python genericagent/mcp_server/tests/manual_sse_check.py
"""

from __future__ import annotations

import os

import anyio
from mcp import ClientSession
from mcp.client.sse import sse_client


async def main() -> None:
    token = os.environ.get("GA_MCP_TOKEN", "")
    if not token:
        raise SystemExit("GA_MCP_TOKEN is required")
    url = os.environ.get("GA_MCP_TEST_URL", "http://127.0.0.1:5050/sse")
    headers = {"Authorization": f"Bearer {token}"}
    async with sse_client(url, headers=headers, timeout=5, sse_read_timeout=10) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("tools:", [tool.name for tool in tools.tools])
            status = await session.call_tool("ga_status", {})
            print(status.content[0].text)


if __name__ == "__main__":
    anyio.run(main)
