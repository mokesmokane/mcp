"""
Entry point for HTTP/SSE transport MCP server.
Use this to expose your MCP server on the internet for OpenAI Responses API.
"""
import uvicorn
from test_mcp.http_server import create_http_app

app = create_http_app()

if __name__ == "__main__":
    uvicorn.run(
        "main_http:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
