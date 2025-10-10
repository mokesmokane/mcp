"""
HTTP/SSE transport for remote MCP server access.
This allows OpenAI Responses API and other remote clients to call your MCP server.
"""
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional, AsyncIterator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import json
import os

from .tools import search_items_tool, get_item_tool, health_tool, save_documentation_tool, get_documentation_tool


# Rate limiter
limiter = Limiter(key_func=get_remote_address)


# Request/Response models
class ListToolsRequest(BaseModel):
    """Request to list available tools."""
    action: str = Field("list_tools")


class ToolDefinition(BaseModel):
    """MCP tool definition."""
    name: str
    description: str
    inputSchema: Dict[str, Any]  # camelCase per MCP spec
    outputSchema: Dict[str, Any] = Field(default_factory=dict)  # Optional output schema


class ListToolsResponse(BaseModel):
    """Response containing available tools."""
    tools: List[ToolDefinition]


class CallToolRequest(BaseModel):
    """Request to call a specific tool."""
    action: str = Field("call_tool")
    name: str
    arguments: Dict[str, Any] = {}


class CallToolResponse(BaseModel):
    """Response from a tool call."""
    output: str  # JSON string


# Authentication
def verify_auth(authorization: Optional[str] = Header(None)) -> str:
    """
    Verify Bearer token authentication.
    Replace this with your actual auth logic (OAuth, JWT, API keys, etc.)
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization scheme. Use Bearer token.")

    if not token:
        raise HTTPException(status_code=401, detail="Missing token")

    # Strip quotes if present (some clients send "Bearer \"token\"")
    token = token.strip('"')

    # TODO: Validate token against your auth system
    # For now, just check if it matches an environment variable (for testing)
    expected_token = os.getenv("MCP_API_KEY", "")
    if expected_token and token != expected_token:
        raise HTTPException(status_code=403, detail="Invalid token")

    return token


# Tool registry
def get_tool_definitions() -> List[ToolDefinition]:
    """Return all available tool definitions."""
    return [
        ToolDefinition(
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
                "required": ["query"],
                "additionalProperties": False
            }
        ),
        ToolDefinition(
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
                "required": ["id"],
                "additionalProperties": False
            }
        ),
        ToolDefinition(
            name="health",
            description="Check the health status of the server and any upstream dependencies.",
            inputSchema={
                "type": "object",
                "properties": {},
                "additionalProperties": False
            }
        ),
        ToolDefinition(
            name="get_documentation",
            description="Retrieve API documentation from the database by ID. Use this to fetch full documentation details after finding relevant docs via semantic search.",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "The UUID of the documentation record to retrieve"
                    }
                },
                "required": ["id"],
                "additionalProperties": False
            },
            outputSchema={
                "type": "object",
                "properties": {
                    "success": {
                        "type": "boolean",
                        "description": "Whether the request succeeded"
                    },
                    "id": {
                        "type": "string",
                        "description": "The UUID of the documentation"
                    },
                    "formatted_documentation": {
                        "type": "string",
                        "description": "Human-readable markdown formatted documentation"
                    },
                    "raw_data": {
                        "type": "object",
                        "description": "Raw database record with all fields"
                    },
                    "error": {
                        "type": "string",
                        "description": "Error message if success is false"
                    }
                },
                "required": ["success"]
            }
        ),
        ToolDefinition(
            name="save_documentation",
            description="Save API documentation to the database and upload to OpenAI vector store for semantic search. Use this to store detailed documentation about API endpoints.",
            inputSchema={
                "type": "object",
                "properties": {
                    "api_name": {
                        "type": "string",
                        "description": "Name of the API (e.g., 'Stripe', 'OpenAI')"
                    },
                    "endpoint_path": {
                        "type": "string",
                        "description": "The endpoint path (e.g., '/v1/chat/completions')"
                    },
                    "http_method": {
                        "type": "string",
                        "description": "HTTP method (GET, POST, PUT, DELETE, etc.)"
                    },
                    "category": {
                        "type": "string",
                        "description": "Short category string for organizing documentation"
                    },
                    "title": {
                        "type": "string",
                        "description": "Human-readable title for the endpoint"
                    },
                    "documentation": {
                        "type": "string",
                        "description": "The full documentation text"
                    },
                    "short_description": {
                        "type": "string",
                        "description": "Short description for vector store semantic search (will be uploaded to OpenAI with metadata)"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional array of tags for filtering"
                    },
                    "version": {
                        "type": "string",
                        "description": "Optional API version (e.g., 'v1', '2024-01-15')"
                    },
                    "examples": {
                        "type": "object",
                        "description": "Optional JSON object with code examples"
                    },
                    "parameters": {
                        "type": "object",
                        "description": "Optional JSON object describing parameters"
                    },
                    "source_url": {
                        "type": "string",
                        "description": "Optional URL to original documentation"
                    }
                },
                "required": ["api_name", "documentation"],
                "additionalProperties": False
            },
            outputSchema={
                "type": "object",
                "properties": {
                    "success": {
                        "type": "boolean",
                        "description": "Whether the save operation succeeded"
                    },
                    "id": {
                        "type": "string",
                        "description": "The UUID of the created documentation record"
                    },
                    "vector_store_file_id": {
                        "type": "string",
                        "description": "OpenAI vector store file ID (if uploaded)"
                    },
                    "message": {
                        "type": "string",
                        "description": "Human-readable success or error message"
                    },
                    "error": {
                        "type": "string",
                        "description": "Detailed error message if success is false"
                    }
                },
                "required": ["success", "message"]
            }
        )
    ]


async def execute_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a tool and return its result."""
    if name == "search_items":
        return await search_items_tool(arguments)
    elif name == "get_item":
        return await get_item_tool(arguments)
    elif name == "health":
        return await health_tool(arguments)
    elif name == "get_documentation":
        return await get_documentation_tool(arguments)
    elif name == "save_documentation":
        return await save_documentation_tool(arguments)
    else:
        raise HTTPException(status_code=404, detail=f"Unknown tool: {name}")


# Create FastAPI app
def create_http_app() -> FastAPI:
    """Create the FastAPI application for HTTP/SSE transport."""
    app = FastAPI(
        title="Test MCP Server (HTTP)",
        description="Remote MCP server accessible via HTTP/SSE for OpenAI Responses API",
        version="0.1.0"
    )
    
    # Add rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    
    # CORS (usually not needed for server-to-server, but safe to have)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        print(f"DEBUG: Expected token: {os.getenv('MCP_API_KEY', 'NOT_SET')}")
        return {"status": "healthy", "transport": "http"}
    
    @app.post("/mcp")
    @limiter.limit("100/minute")
    async def mcp_endpoint(
        request: Request,
        payload: Dict[str, Any],
        token: str = Header(None, alias="Authorization")
    ):
        """
        Main MCP endpoint supporting JSON-RPC 2.0 protocol.
        Compatible with OpenAI Responses API.
        """
        # Debug logging
        print(f"DEBUG: Received Authorization header: {token}")
        print(f"DEBUG: Expected token: {os.getenv('MCP_API_KEY', 'NOT_SET')}")
        print(f"DEBUG: Payload: {payload}")

        # Verify authentication
        if token:
            verify_auth(token)

        # Handle JSON-RPC 2.0 format
        jsonrpc = payload.get("jsonrpc")
        method = payload.get("method")
        rpc_id = payload.get("id")
        params = payload.get("params", {})

        if jsonrpc != "2.0":
            return JSONResponse(
                status_code=400,
                content={
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "error": {"code": -32600, "message": "Invalid Request - not JSON-RPC 2.0"}
                }
            )

        # Handle notifications (no id, no response expected)
        if rpc_id is None:
            print(f"DEBUG: Received notification: {method}")
            # Just acknowledge notifications with 200 OK
            return JSONResponse(content={"ok": True})

        # Handle initialize
        if method == "initialize":
            return JSONResponse(content={
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "test-mcp-server",
                        "version": "0.1.0"
                    }
                }
            })

        # Handle tools/list
        elif method == "tools/list":
            tools = get_tool_definitions()
            return JSONResponse(content={
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {
                    "tools": [t.model_dump() for t in tools]
                }
            })

        # Handle tools/call
        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})

            try:
                result = await execute_tool(tool_name, arguments)
                return JSONResponse(content={
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(result)
                            }
                        ]
                    }
                })
            except HTTPException as e:
                return JSONResponse(
                    status_code=e.status_code,
                    content={
                        "jsonrpc": "2.0",
                        "id": rpc_id,
                        "error": {"code": -32603, "message": e.detail}
                    }
                )
            except Exception as e:
                return JSONResponse(
                    status_code=500,
                    content={
                        "jsonrpc": "2.0",
                        "id": rpc_id,
                        "error": {"code": -32603, "message": f"Internal error: {str(e)}"}
                    }
                )

        else:
            return JSONResponse(
                status_code=400,
                content={
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"}
                }
            )
    
    @app.post("/mcp/sse")
    @limiter.limit("100/minute")
    async def mcp_sse_endpoint(
        request: Request,
        payload: Dict[str, Any],
        token: str = Header(None, alias="Authorization")
    ):
        """
        SSE (Server-Sent Events) endpoint for MCP.
        Alternative transport that some clients prefer.
        """
        # Verify authentication
        if token:
            verify_auth(token)
        
        action = payload.get("action")
        
        # List tools
        if action == "list_tools":
            tools = get_tool_definitions()
            response = ListToolsResponse(tools=tools)
            
            async def stream_sse() -> AsyncIterator[bytes]:
                data = json.dumps(response.model_dump())
                yield f"data: {data}\n\n".encode("utf-8")
            
            return StreamingResponse(stream_sse(), media_type="text/event-stream")
        
        # Call tool
        elif action == "call_tool":
            try:
                req = CallToolRequest(**payload)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid request: {str(e)}")
            
            try:
                result = await execute_tool(req.name, req.arguments)
                
                async def stream_sse() -> AsyncIterator[bytes]:
                    output = CallToolResponse(
                        output=json.dumps(result, separators=(",", ":"))
                    )
                    data = json.dumps(output.model_dump())
                    yield f"data: {data}\n\n".encode("utf-8")
                
                return StreamingResponse(stream_sse(), media_type="text/event-stream")
            
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Tool execution failed: {str(e)}")
        
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported action: {action}")
    
    return app
