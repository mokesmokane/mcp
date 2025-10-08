# Test MCP Server

A **dual-transport Model Context Protocol (MCP) server** that exposes your API as tools to LLM clients.

**Supports two transports:**
- **Stdio** (local): For Claude Desktop, Cursor, Windsurf
- **HTTP/SSE** (remote): For OpenAI Responses API and web clients

## What is MCP?

The Model Context Protocol (MCP) is a standard that connects AI systems with external tools and data sources. MCP servers expose **tools** (functions), **resources** (data), and **prompts** that LLMs can use via a JSON-RPC interface over stdio.

## Architecture

This is a **proper MCP server** that:
- ✅ Supports **dual transports**: stdio (local) and HTTP/SSE (remote)
- ✅ Uses the official **MCP Python SDK** (`mcp` package) for stdio
- ✅ Uses **FastAPI** for HTTP/SSE transport
- ✅ Can be launched by MCP clients (Claude Desktop, Cursor, Windsurf)
- ✅ Can be called remotely by OpenAI Responses API
- ✅ Exposes tools with strict JSON schemas for deterministic behavior
- ✅ Includes authentication, rate limiting, and security best practices
- ✅ Follows SOLID principles with clean separation of concerns

## Project Structure

```
windsurf-project/
├── main.py                    # Entry point for stdio transport (local)
├── main_http.py               # Entry point for HTTP/SSE transport (remote)
├── requirements.txt           # Python dependencies
├── mcp_config.json           # Configuration for local MCP clients
├── .env.example              # Environment variables template
├── README.md                 # This file
├── REMOTE_DEPLOYMENT.md      # Guide for deploying as remote server
├── ThingsIveLearned.md       # Project patterns and insights
└── test_mcp/                 # Main package
    ├── __init__.py           # Package initialization
    ├── server.py             # MCP server (stdio transport)
    ├── http_server.py        # MCP server (HTTP/SSE transport)
    ├── tools.py              # Tool implementations (shared)
    ├── config.py             # Configuration settings
    └── handlers.py           # Legacy handlers (can be removed)
```

## Installation

1. **Install dependencies**:
```bash
pip install -r requirements.txt
```

2. **Configure environment** (optional):
```bash
cp .env.example .env
# Edit .env with your API credentials if needed
```

## Available Tools

### 1. `search_items`
Search for items with pagination support.

**Input Schema**:
```json
{
  "query": "search term",      // required
  "limit": 10,                  // optional, 1-50, default 10
  "cursor": "pagination_token"  // optional
}
```

**Output**:
```json
{
  "items": [
    {
      "id": "item_001",
      "title": "Item Title",
      "summary": "Brief description",
      "score": 0.95
    }
  ],
  "nextCursor": "next_page_token",
  "total": 42
}
```

### 2. `get_item`
Retrieve detailed information about a single item.

**Input Schema**:
```json
{
  "id": "item_001"  // required
}
```

**Output**:
```json
{
  "id": "item_001",
  "title": "Item Title",
  "body": "Full content...",
  "createdAt": "2025-10-08T08:00:00Z",
  "url": "https://example.com/items/item_001",
  "metadata": {
    "author": "Author Name",
    "tags": ["tag1", "tag2"]
  }
}
```

### 3. `health`
Check server health status.

**Input Schema**: `{}` (no parameters)

**Output**:
```json
{
  "status": "healthy",
  "server": "test-mcp-server",
  "version": "0.1.0",
  "timestamp": "2025-10-08T08:43:00Z"
}
```

## Usage

### Local Usage (Stdio Transport)

#### Testing Manually

Run the stdio server:
```bash
python main.py
```

Then send a JSON-RPC request via stdin:
```json
{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}
```

#### Connecting to Claude Desktop

1. Open your Claude Desktop config file:
   - **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

2. Add this server configuration:
```json
{
  "mcpServers": {
    "test-mcp-server": {
      "command": "python",
      "args": [
        "/Users/mokes/CascadeProjects/windsurf-project/main.py"
      ],
      "env": {
        "API_BASE_URL": "http://localhost:8000/api/v1",
        "API_KEY": ""
      }
    }
  }
}
```

3. Restart Claude Desktop

4. The tools will appear in Claude's tool palette

#### Connecting to Cursor/Windsurf

Add the server to your MCP configuration (similar process to Claude Desktop).

---

### Remote Usage (HTTP/SSE Transport)

#### Quick Start

1. **Start the HTTP server:**
```bash
python main_http.py
```

Server runs at `http://localhost:8000`

2. **Test with curl:**
```bash
# List tools
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"action": "list_tools"}'

# Call a tool
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "action": "call_tool",
    "name": "search_items",
    "arguments": {"query": "test", "limit": 5}
  }'
```

#### Using with OpenAI Responses API

Once deployed to a public URL:

```python
from openai import OpenAI

client = OpenAI()

resp = client.responses.create(
    model="gpt-5",
    tools=[{
        "type": "mcp",
        "server_label": "my-api",
        "server_url": "https://api.yourdomain.com/mcp",
        "authorization": "Bearer your_token",
        "require_approval": "never"
    }],
    input="Search for items about AI"
)

print(resp.output_text)
```

**See [REMOTE_DEPLOYMENT.md](REMOTE_DEPLOYMENT.md) for complete deployment guide.**

## Customizing for Your API

### Option 1: Replace Mock Data with Real API Calls

Edit `test_mcp/tools.py` and uncomment the real API call examples:

```python
async def search_items_tool(arguments: Dict[str, Any]) -> Dict[str, Any]:
    query = arguments.get("query", "")
    limit = arguments.get("limit", 10)
    cursor = arguments.get("cursor")
    
    # Call your actual API
    params = {"q": query, "limit": limit}
    if cursor:
        params["cursor"] = cursor
    
    data = await call_api("GET", "/search", params=params)
    
    return {
        "items": data.get("items", []),
        "nextCursor": data.get("nextCursor"),
        "total": data.get("total", 0)
    }
```

### Option 2: Add New Tools

1. **Define the tool schema** in `test_mcp/server.py`:
```python
Tool(
    name="create_item",
    description="Create a new item",
    inputSchema={
        "type": "object",
        "properties": {
            "title": {"type": "string", "minLength": 1},
            "body": {"type": "string"}
        },
        "required": ["title"]
    }
)
```

2. **Implement the tool** in `test_mcp/tools.py`:
```python
async def create_item_tool(arguments: Dict[str, Any]) -> Dict[str, Any]:
    title = arguments.get("title")
    body = arguments.get("body", "")
    
    # Your implementation
    data = await call_api("POST", "/items", json={"title": title, "body": body})
    return data
```

3. **Wire it up** in the `call_tool` handler:
```python
elif name == "create_item":
    result = await create_item_tool(arguments)
    return [TextContent(type="text", text=json.dumps(result, indent=2))]
```

## Best Practices

### ✅ DO:
- **Keep tool outputs compact and stable** - LLMs rely on predictable shapes
- **Use opaque cursors** for pagination (not page numbers)
- **Validate inputs strictly** with JSON schemas (min/max, enums, defaults)
- **Return clear error messages** - avoid HTML or stack traces
- **Add timeouts and retries** for external API calls
- **Never expose secrets** in tool outputs

### ❌ DON'T:
- Don't return huge blobs of data - summarize or paginate
- Don't use page numbers - use cursors for deterministic pagination
- Don't hardcode API keys - use environment variables
- Don't expose internal IDs or PII unless required
- Don't make tools that have side effects without idempotency keys

## Key Patterns

1. **Separation of Concerns**:
   - `server.py`: MCP protocol handling (stdio, JSON-RPC)
   - `tools.py`: Business logic and API calls
   - `config.py`: Configuration management

2. **Type Safety**:
   - Pydantic models for validation
   - Python type hints throughout
   - Strict JSON schemas for tool inputs

3. **Error Handling**:
   - Graceful degradation
   - Clear error messages
   - Timeout handling

4. **Determinism**:
   - Stable output formats
   - Predictable pagination
   - Consistent error codes

## Troubleshooting

### Server won't start
- Check Python version (3.10+)
- Verify all dependencies installed: `pip install -r requirements.txt`
- Check for syntax errors: `python -m py_compile main.py`

### Tools not appearing in Claude Desktop
- Verify the path in `claude_desktop_config.json` is absolute
- Check Claude Desktop logs for errors
- Restart Claude Desktop after config changes

### API calls failing
- Verify `API_BASE_URL` and `API_KEY` in environment
- Check network connectivity
- Add logging to `tools.py` to debug

## Environment Variables

- `API_BASE_URL`: Base URL for your API (default: `http://localhost:8000/api/v1`)
- `API_KEY`: API authentication key (optional)
- `ENVIRONMENT`: Environment name (default: `development`)
- `DEBUG`: Enable debug logging (default: `true`)

## License

MIT

## Contributing

1. Follow SOLID principles
2. Add type hints to all functions
3. Update `ThingsIveLearned.md` with new patterns
4. Test with Claude Desktop before committing
