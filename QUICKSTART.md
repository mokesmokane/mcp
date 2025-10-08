# MCP Server Quick Start

## What You Have

A **dual-transport MCP server** that works with:
- ✅ **Local clients**: Claude Desktop, Cursor, Windsurf (stdio)
- ✅ **Remote clients**: OpenAI Responses API (HTTP/SSE)

## 5-Minute Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Choose Your Transport

#### Option A: Local (Stdio) - For Claude Desktop/Cursor
```bash
python main.py
```

Then configure in Claude Desktop:
```json
{
  "mcpServers": {
    "test-mcp-server": {
      "command": "python",
      "args": ["/absolute/path/to/main.py"]
    }
  }
}
```

#### Option B: Remote (HTTP) - For OpenAI API
```bash
python main_http.py
```

Test it:
```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"action": "list_tools"}'
```

## Available Tools

1. **search_items** - Search with pagination
2. **get_item** - Fetch item by ID
3. **health** - Server health check

## Next Steps

### For Local Development
- Tools currently return **mock data**
- Edit `test_mcp/tools.py` to connect to your real API
- Add more tools as needed

### For Production Deployment
1. Set `MCP_API_KEY` environment variable
2. Deploy to Railway/Render/VPS (see `REMOTE_DEPLOYMENT.md`)
3. Use with OpenAI:

```python
from openai import OpenAI

client = OpenAI()
resp = client.responses.create(
    model="gpt-5",
    tools=[{
        "type": "mcp",
        "server_url": "https://your-domain.com/mcp",
        "authorization": "Bearer your_token",
        "server_label": "my-api"
    }],
    input="Search for AI tools"
)
```

## Documentation

- **README.md** - Full feature documentation
- **REMOTE_DEPLOYMENT.md** - Deployment guide for HTTP/SSE
- **ThingsIveLearned.md** - Architecture patterns and insights

## File Structure

```
├── main.py              # Stdio transport (local)
├── main_http.py         # HTTP/SSE transport (remote)
├── test_mcp/
│   ├── server.py        # Stdio server
│   ├── http_server.py   # HTTP/SSE server
│   └── tools.py         # Tool implementations (shared)
├── Dockerfile           # Docker deployment
└── Procfile            # Railway/Render deployment
```

## Common Issues

**"401 Unauthorized"** - Set `MCP_API_KEY` in environment

**"Tools not appearing"** - Check absolute path in config file

**"Connection refused"** - Ensure server is running on correct port

## Support

- Check `ThingsIveLearned.md` for patterns and best practices
- See `REMOTE_DEPLOYMENT.md` for deployment troubleshooting
- Review tool implementations in `test_mcp/tools.py`
