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

from .tools import search_items_tool, get_item_tool, health_tool


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
    input_schema: Dict[str, Any]


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
            input_schema={
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
            input_schema={
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
            input_schema={
                "type": "object",
                "properties": {},
                "additionalProperties": False
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
        return {"status": "healthy", "transport": "http"}
    
    @app.post("/mcp")
    @limiter.limit("100/minute")
    async def mcp_endpoint(
        request: Request,
        payload: Dict[str, Any],
        token: str = Header(None, alias="Authorization")
    ):
        """
        Main MCP endpoint supporting both list_tools and call_tool actions.
        Supports both JSON and SSE responses.
        """
        # Debug logging
        import logging
        logging.info(f"Received Authorization header: {token}")
        logging.info(f"Expected token: {os.getenv('MCP_API_KEY', 'NOT_SET')}")

        # Verify authentication
        if token:
            verify_auth(token)
        
        action = payload.get("action")
        
        # List tools
        if action == "list_tools":
            tools = get_tool_definitions()
            response = ListToolsResponse(tools=tools)
            return JSONResponse(content=response.model_dump())
        
        # Call tool
        elif action == "call_tool":
            try:
                req = CallToolRequest(**payload)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid request: {str(e)}")
            
            # Execute tool
            try:
                result = await execute_tool(req.name, req.arguments)
                
                # Return as streaming response (chunked transfer)
                async def stream() -> AsyncIterator[bytes]:
                    output = CallToolResponse(
                        output=json.dumps(result, separators=(",", ":"))
                    )
                    yield (json.dumps(output.model_dump()) + "\n").encode("utf-8")
                
                return StreamingResponse(stream(), media_type="application/json")
            
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Tool execution failed: {str(e)}")
        
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported action: {action}")
    
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
