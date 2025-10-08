"""
MCP Server implementation using stdio transport.
This server communicates via JSON-RPC over stdin/stdout.
"""
import asyncio
import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .tools import search_items_tool, get_item_tool, health_tool


async def main():
    """Main entry point for the MCP server."""
    # Create the MCP server instance
    server = Server("test-mcp-server")
    
    # Register tools
    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List available tools."""
        return [
            Tool(
                name="search_items",
                description="Search for items in the database. Returns a list of matching items with pagination support.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query string",
                            "minLength": 1
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results to return",
                            "minimum": 1,
                            "maximum": 50,
                            "default": 10
                        },
                        "cursor": {
                            "type": "string",
                            "description": "Pagination cursor for fetching next page"
                        }
                    },
                    "required": ["query"]
                }
            ),
            Tool(
                name="get_item",
                description="Retrieve a single item by its ID. Returns detailed information about the item.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "string",
                            "description": "Unique identifier of the item",
                            "minLength": 1
                        }
                    },
                    "required": ["id"]
                }
            ),
            Tool(
                name="health",
                description="Check the health status of the server and any upstream dependencies.",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            )
        ]
    
    @server.call_tool()
    async def call_tool(name: str, arguments: Any) -> list[TextContent]:
        """Handle tool calls."""
        if name == "search_items":
            result = await search_items_tool(arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "get_item":
            result = await get_item_tool(arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "health":
            result = await health_tool(arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
        else:
            raise ValueError(f"Unknown tool: {name}")
    
    # Run the server with stdio transport
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )
