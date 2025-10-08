"""
Main entry point for the Test MCP Server.
This is a stdio-based MCP server that communicates via JSON-RPC.
"""
import asyncio
from test_mcp.server import main

if __name__ == "__main__":
    asyncio.run(main())
