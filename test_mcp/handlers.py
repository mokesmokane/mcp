"""
Request handlers for the MCP server.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

router = APIRouter()

class MCPRequest(BaseModel):
    """Base model for MCP requests."""
    method: str
    params: Optional[Dict[str, Any]] = None
    id: Optional[str] = None
    jsonrpc: str = "2.0"

class MCPResponse(BaseModel):
    """Base model for MCP responses."""
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    id: Optional[str] = None
    jsonrpc: str = "2.0"

@router.post("/rpc")
async def handle_rpc(request: MCPRequest) -> MCPResponse:
    """Handle MCP RPC requests."""
    try:
        # Here you would typically route to different handlers based on request.method
        if request.method == "test.echo":
            return MCPResponse(
                result={"echo": request.params},
                id=request.id
            )
        elif request.method == "test.add":
            if not request.params or 'a' not in request.params or 'b' not in request.params:
                raise HTTPException(status_code=400, detail="Missing parameters 'a' and 'b'")
            return MCPResponse(
                result={"sum": request.params['a'] + request.params['b']},
                id=request.id
            )
        else:
            raise HTTPException(status_code=404, detail=f"Method '{request.method}' not found")
    except Exception as e:
        return MCPResponse(
            error={
                "code": -32603,
                "message": f"Internal error: {str(e)}",
                "data": None
            },
            id=request.id
        )

@router.get("/openrpc.json")
async def get_openrpc_schema() -> Dict[str, Any]:
    """Return the OpenRPC schema for this MCP server."""
    return {
        "openrpc": "1.2.0",
        "info": {
            "version": "0.1.0",
            "title": "Test MCP Server",
            "description": "A test implementation of the Model Context Protocol (MCP) server",
        },
        "methods": [
            {
                "name": "test.echo",
                "description": "Echo back the input parameters",
                "params": [
                    {
                        "name": "params",
                        "schema": {
                            "type": "object",
                            "additionalProperties": True
                        }
                    }
                ],
                "result": {
                    "name": "echo",
                    "schema": {
                        "type": "object",
                        "additionalProperties": True
                    }
                }
            },
            {
                "name": "test.add",
                "description": "Add two numbers",
                "params": [
                    {
                        "name": "a",
                        "schema": {"type": "number"}
                    },
                    {
                        "name": "b",
                        "schema": {"type": "number"}
                    }
                ],
                "result": {
                    "name": "sum",
                    "schema": {"type": "number"}
                }
            }
        ]
    }
