# Test MCP Server Project

## What This Is
A **dual-transport MCP (Model Context Protocol) server** that exposes tools to LLM clients.

**Two transports:**
1. **Stdio** (local): For Claude Desktop, Cursor, Windsurf - communicates via JSON-RPC over stdin/stdout
2. **HTTP/SSE** (remote): For OpenAI Responses API - communicates via HTTP with JSON or Server-Sent Events

## Project Structure
- `main.py`: Entry point for stdio transport (local MCP clients)
- `main_http.py`: Entry point for HTTP/SSE transport (remote/OpenAI)
- `requirements.txt`: Python dependencies (mcp SDK + FastAPI)
- `mcp_config.json`: Configuration for local MCP clients (Claude Desktop, etc.)
- `.env.example`: Environment variables template
- `Dockerfile`: Docker container configuration
- `Procfile`: Deployment configuration (Railway, Render, Heroku)
- `REMOTE_DEPLOYMENT.md`: Complete guide for deploying as remote server
- `test_mcp/`: Package containing MCP server implementation
  - `__init__.py`: Package initialization
  - `server.py`: MCP server implementation (stdio transport)
  - `http_server.py`: MCP server implementation (HTTP/SSE transport)
  - `tools.py`: Tool implementations (shared by both transports)
  - `config.py`: Configuration settings
  - `handlers.py`: Legacy handlers (can be removed)

## Dependencies
- **mcp**: Official MCP Python SDK for stdio-based servers
- **fastapi**: Web framework for HTTP/SSE transport
- **uvicorn**: ASGI server for FastAPI
- **slowapi**: Rate limiting middleware
- **pydantic**: Data validation and settings management
- **httpx**: Async HTTP client for calling external APIs
- **python-dotenv**: Environment variable management

## Key Patterns

### 1. Dual Transport Architecture
**Stdio Transport (for local clients):**
- MCP clients (Claude Desktop, Cursor) expect **stdio** communication
- Server reads JSON-RPC requests from stdin
- Server writes JSON-RPC responses to stdout
- Uses `mcp.server.stdio.stdio_server()` for transport
- Entry point: `main.py`

**HTTP/SSE Transport (for remote clients):**
- OpenAI Responses API expects **HTTP** communication
- Server exposes `/mcp` endpoint for JSON responses
- Server exposes `/mcp/sse` endpoint for Server-Sent Events
- Uses FastAPI for web server
- Supports both `list_tools` and `call_tool` actions
- Entry point: `main_http.py`

### 2. Tool Registration
- Tools are registered with strict JSON schemas
- Each tool has: name, description, inputSchema
- Schemas enforce: types, min/max, required fields, defaults
- LLMs rely on these schemas for deterministic behavior

### 3. Separation of Concerns (SOLID)
- `server.py`: Protocol handling for stdio transport
- `http_server.py`: Protocol handling for HTTP/SSE transport
- `tools.py`: Business logic (shared by both transports)
- `config.py`: Configuration management
- Clean interfaces between layers - tools are transport-agnostic

### 4. Type Safety
- Python type hints throughout
- Pydantic models for validation
- JSON schemas for tool inputs
- Explicit return types

### 5. Error Handling
- Graceful degradation
- Clear, short error messages (no HTML/stack traces)
- Timeout handling for external APIs
- Never expose secrets in outputs

### 6. Pagination Pattern
- Use **opaque cursors**, not page numbers
- Return `nextCursor` in responses
- LLMs can loop deterministically until `nextCursor=null`

## How to Run

### Local (Stdio Transport)
1. Install dependencies: `pip install -r requirements.txt`
2. Test locally: `python main.py` (reads from stdin)
3. Connect to Claude Desktop: Add config to `claude_desktop_config.json`
4. Restart Claude Desktop - tools will appear

### Remote (HTTP/SSE Transport)
1. Install dependencies: `pip install -r requirements.txt`
2. Start server: `python main_http.py`
3. Test with curl: `curl -X POST http://localhost:8000/mcp -d '{"action":"list_tools"}'`
4. Deploy to internet: See `REMOTE_DEPLOYMENT.md`
5. Use with OpenAI: Pass `server_url` in Responses API

## Available Tools
1. **search_items**: Search with pagination (query, limit, cursor)
2. **get_item**: Fetch single item by ID
3. **health**: Server health check

## Tool Implementation Notes

### Mock vs Real Data
- Current implementation uses **mock data** in `tools.py`
- To connect to real API: uncomment the `call_api()` examples
- Set `API_BASE_URL` and `API_KEY` in environment

### Adding New Tools
1. Implement logic in `tools.py` → `new_tool_function()`
2. Define schema in `server.py` → `list_tools()` (stdio)
3. Define schema in `http_server.py` → `get_tool_definitions()` (HTTP)
4. Wire up in both `server.py` and `http_server.py` → `call_tool()` handlers
5. Keep schemas identical across both transports

### Best Practices for Tools
- ✅ Keep outputs compact and stable
- ✅ Use strict schemas (min/max, enums, defaults)
- ✅ Return structured JSON, not prose
- ✅ Use cursors for pagination
- ✅ Add timeouts for external calls
- ❌ Don't return huge blobs
- ❌ Don't expose secrets/PII
- ❌ Don't use page numbers

## MCP Client Configuration

### Claude Desktop
Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "test-mcp-server": {
      "command": "python",
      "args": ["/absolute/path/to/main.py"],
      "env": {"API_KEY": "..."}
    }
  }
}
```

### Cursor/Windsurf
Similar configuration in their respective config files.

## Key Learnings

### Why Two Transports?
- **Local MCP clients** (Claude Desktop, Cursor) launch servers as **child processes**
  - They communicate via **stdio** (stdin/stdout), not HTTP
  - Can't call HTTP endpoints directly
  - Need `main.py` with stdio transport

- **Remote clients** (OpenAI Responses API) make **HTTP requests**
  - They call public URLs over the internet
  - Can't launch child processes
  - Need `main_http.py` with HTTP/SSE transport

### Architecture Options
1. **Dual transport** (current): Same tools, two entry points
2. **MCP + Backend API**: MCP servers proxy to your existing HTTP API
3. **Hybrid**: Some tools self-contained, others call external APIs

### Common Pitfalls
- ❌ Building HTTP server instead of stdio server
- ❌ Using page numbers instead of cursors
- ❌ Returning unstructured text instead of JSON
- ❌ Not validating inputs with schemas
- ❌ Exposing secrets in tool outputs
- ❌ Forgetting to use absolute paths in client config

## Testing Strategy

### Stdio Transport
1. **Manual**: Run `python main.py` and send JSON-RPC via stdin
2. **Integration**: Connect to Claude Desktop and test tools
3. **Unit**: Test individual tool functions in `tools.py`

### HTTP/SSE Transport
1. **Local**: Run `python main_http.py` and test with curl
2. **OpenAI**: Deploy and test with Responses API
3. **Load**: Test rate limiting and concurrent requests

## Environment Variables
- `API_BASE_URL`: External API base URL (if using)
- `API_KEY`: API authentication key (if using)
- `MCP_API_KEY`: Bearer token for HTTP/SSE auth (required for production)
- `ENVIRONMENT`: development/production
- `DEBUG`: Enable debug logging

## Security Considerations

### HTTP/SSE Transport
- **Authentication**: Bearer token via `Authorization` header
- **Rate Limiting**: 100 requests/minute per IP (configurable)
- **HTTPS**: Always use TLS in production
- **Input Validation**: Strict JSON schemas on all tools
- **Output Sanitization**: Never expose secrets or PII
- **Logging**: Log tool calls but not sensitive data

### Stdio Transport
- **No network exposure**: Runs locally as child process
- **Trust boundary**: Only accessible to local MCP clients
- **No auth needed**: Client controls server lifecycle

## Deployment Options

### Local Development
- Stdio: `python main.py`
- HTTP: `python main_http.py`

### Production (HTTP/SSE)
1. **Docker**: `docker build -t mcp-server . && docker run -p 8000:8000 mcp-server`
2. **Railway/Render**: Push to GitHub, connect repo, set env vars
3. **VPS**: systemd service + nginx reverse proxy + Let's Encrypt
4. **Serverless**: AWS Lambda/Google Cloud Functions with Mangum adapter

See `REMOTE_DEPLOYMENT.md` for detailed deployment guides.

## Next Steps
- [ ] Replace mock data with real API calls in `tools.py`
- [ ] Add more tools (create, update, delete operations)
- [ ] Add idempotency keys for write operations
- [ ] Implement OAuth 2.0 for better auth
- [ ] Add comprehensive error handling and retries
- [ ] Add structured logging for debugging
- [ ] Add unit tests for tools
- [ ] Set up monitoring and alerts
- [ ] Create CI/CD pipeline
- [ ] Deploy to production environment

## Quick Reference

### Start Servers
```bash
# Stdio (local)
python main.py

# HTTP/SSE (remote)
python main_http.py
```

### Test Endpoints
```bash
# List tools
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"action": "list_tools"}'

# Call tool
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_token" \
  -d '{
    "action": "call_tool",
    "name": "search_items",
    "arguments": {"query": "test", "limit": 5}
  }'
```

### OpenAI Integration
```python
from openai import OpenAI

client = OpenAI()
resp = client.responses.create(
    model="gpt-5",
    tools=[{
        "type": "mcp",
        "server_url": "https://api.yourdomain.com/mcp",
        "authorization": "Bearer your_token",
        "server_label": "my-api",
        "require_approval": "never"
    }],
    input="Your prompt here"
)
```
