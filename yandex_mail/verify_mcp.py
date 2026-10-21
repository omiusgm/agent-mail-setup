"""Verify real MCP stdio handshake and exposed tools; no mailbox credentials used."""
import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def verify():
    params = StdioServerParameters(command=sys.executable,
                                   args=[str(Path(__file__).with_name("server.py"))])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            initialized = await session.initialize()
            listed = await session.list_tools()
            names = {tool.name for tool in listed.tools}
            assert names == {"connection_status", "list_folders", "search_emails", "read_email", "download_attachment"}
            for tool in listed.tools:
                if tool.name != "download_attachment":
                    assert tool.annotations.readOnlyHint is True
            print("MCP handshake OK:", initialized.serverInfo.name)
            print("Tools:", ", ".join(sorted(names)))
            print("No mailbox operations were performed.")


if __name__ == "__main__":
    asyncio.run(asyncio.wait_for(verify(), timeout=20))
