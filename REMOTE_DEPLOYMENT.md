# Remote MCP Server Deployment Guide

This guide shows how to expose your MCP server on the internet so it can be called by **OpenAI's Responses API** and other remote clients.

## Architecture Overview

Your MCP server now supports **two transports**:

1. **Stdio** (local): For Claude Desktop, Cursor, Windsurf
   - Runs as child process
   - Communicates via stdin/stdout
   - Entry point: `main.py`

2. **HTTP/SSE** (remote): For OpenAI Responses API, web clients
   - Runs as web server
   - Communicates via HTTP with JSON or SSE
   - Entry point: `main_http.py`

## Quick Start (Local Testing)

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Set up authentication (optional for testing)
```bash
cp .env.example .env
# Edit .env and set MCP_API_KEY=your_test_token
```

### 3. Start the HTTP server
```bash
python main_http.py
```

Server will be available at `http://localhost:8000`

### 4. Test the endpoints

**List available tools:**
```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_test_token" \
  -d '{"action": "list_tools"}'
```

**Call a tool:**
```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_test_token" \
  -d '{
    "action": "call_tool",
    "name": "search_items",
    "arguments": {"query": "test", "limit": 5}
  }'
```

**Health check:**
```bash
curl http://localhost:8000/health
```

## Using with OpenAI Responses API

Once deployed to a public URL (e.g., `https://api.yourdomain.com`), you can call it from OpenAI:

### Python Example
```python
from openai import OpenAI

client = OpenAI()

resp = client.responses.create(
    model="gpt-5",
    tools=[
        {
            "type": "mcp",
            "server_label": "my-api",
            "server_description": "My custom MCP server for search and retrieval",
            "server_url": "https://api.yourdomain.com/mcp",
            "authorization": "Bearer your_secure_token",
            "require_approval": "never",  # or "always" for sensitive operations
            "allowed_tools": ["search_items", "get_item"]  # optional filter
        }
    ],
    input="Find items about AI and show me the first result"
)

print(resp.output_text)
```

### JavaScript Example
```javascript
import OpenAI from "openai";
const client = new OpenAI();

const resp = await client.responses.create({
  model: "gpt-5",
  tools: [{
    type: "mcp",
    server_label: "my-api",
    server_description: "My custom MCP server for search and retrieval",
    server_url: "https://api.yourdomain.com/mcp",
    authorization: "Bearer your_secure_token",
    require_approval: "never",
    allowed_tools: ["search_items", "get_item"]
  }],
  input: "Find items about AI and show me the first result"
});

console.log(resp.output_text);
```

## Deployment Options

### Option 1: Railway / Render / Fly.io

1. **Create `Procfile`:**
```
web: uvicorn main_http:app --host 0.0.0.0 --port $PORT
```

2. **Set environment variables:**
   - `MCP_API_KEY`: Your secure token
   - `API_BASE_URL`: Your backend API (if using)
   - `API_KEY`: Backend API key (if using)

3. **Deploy:**
   - Railway: `railway up`
   - Render: Connect GitHub repo
   - Fly.io: `fly deploy`

### Option 2: Docker

1. **Create `Dockerfile`:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main_http:app", "--host", "0.0.0.0", "--port", "8000"]
```

2. **Build and run:**
```bash
docker build -t mcp-server .
docker run -p 8000:8000 -e MCP_API_KEY=your_token mcp-server
```

### Option 3: AWS Lambda / Google Cloud Functions

Use **Mangum** adapter for FastAPI:

```bash
pip install mangum
```

```python
# lambda_handler.py
from mangum import Mangum
from main_http import app

handler = Mangum(app)
```

### Option 4: Traditional VPS (DigitalOcean, Linode, etc.)

1. **Install dependencies:**
```bash
sudo apt update
sudo apt install python3-pip nginx certbot python3-certbot-nginx
pip install -r requirements.txt
```

2. **Create systemd service** (`/etc/systemd/system/mcp-server.service`):
```ini
[Unit]
Description=MCP Server
After=network.target

[Service]
User=www-data
WorkingDirectory=/var/www/mcp-server
Environment="PATH=/usr/local/bin"
EnvironmentFile=/var/www/mcp-server/.env
ExecStart=/usr/local/bin/uvicorn main_http:app --host 127.0.0.1 --port 8000

[Install]
WantedBy=multi-user.target
```

3. **Configure Nginx** (`/etc/nginx/sites-available/mcp-server`):
```nginx
server {
    listen 80;
    server_name api.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

4. **Enable HTTPS:**
```bash
sudo certbot --nginx -d api.yourdomain.com
```

5. **Start service:**
```bash
sudo systemctl enable mcp-server
sudo systemctl start mcp-server
```

## Security Checklist

### ✅ Authentication
- [ ] Set `MCP_API_KEY` in environment
- [ ] Use strong, random tokens (32+ characters)
- [ ] Rotate tokens regularly
- [ ] Consider OAuth 2.0 for production

### ✅ Rate Limiting
- [ ] Default: 100 requests/minute per IP
- [ ] Adjust in `http_server.py` if needed
- [ ] Consider per-token limits

### ✅ HTTPS/TLS
- [ ] Always use HTTPS in production
- [ ] Use Let's Encrypt or cloud provider certs
- [ ] Enforce TLS 1.2+ minimum

### ✅ Input Validation
- [ ] All tool schemas have strict validation
- [ ] Min/max constraints on numeric inputs
- [ ] String length limits
- [ ] No arbitrary code execution

### ✅ Output Sanitization
- [ ] Never expose secrets in tool outputs
- [ ] Redact PII if necessary
- [ ] Keep outputs compact and structured

### ✅ Logging & Monitoring
- [ ] Log tool calls (name, args size, latency)
- [ ] Don't log sensitive data
- [ ] Set up alerts for errors/rate limits
- [ ] Monitor for unusual patterns

### ✅ Approvals (OpenAI)
- [ ] Start with `require_approval: "always"`
- [ ] Test thoroughly before setting to "never"
- [ ] Use per-tool approval policies
- [ ] Review approval logs regularly

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `MCP_API_KEY` | No* | Bearer token for authentication. If not set, auth is disabled (dev only) |
| `API_BASE_URL` | No | Base URL if your tools call an external API |
| `API_KEY` | No | API key for external API calls |
| `ENVIRONMENT` | No | `development` or `production` |
| `DEBUG` | No | Enable debug logging |

*Required for production deployments

## Endpoints

### `POST /mcp`
Main MCP endpoint (JSON response, chunked transfer).

**Actions:**
- `list_tools`: Get available tools
- `call_tool`: Execute a tool

### `POST /mcp/sse`
SSE (Server-Sent Events) endpoint. Same actions as `/mcp` but returns `text/event-stream`.

### `GET /health`
Health check endpoint. Returns `{"status": "healthy", "transport": "http"}`.

## Testing with OpenAI

### Step 1: List tools
```python
resp = client.responses.create(
    model="gpt-5",
    tools=[{
        "type": "mcp",
        "server_url": "https://api.yourdomain.com/mcp",
        "authorization": "Bearer your_token",
        "server_label": "test"
    }],
    input="What tools are available?"
)

# Check for mcp_list_tools in output
for item in resp.output:
    if item.get("type") == "mcp_list_tools":
        print(item["tools"])
```

### Step 2: Call a tool
```python
resp = client.responses.create(
    model="gpt-5",
    tools=[{
        "type": "mcp",
        "server_url": "https://api.yourdomain.com/mcp",
        "authorization": "Bearer your_token",
        "server_label": "test",
        "require_approval": "never"
    }],
    input="Search for 'python' and show results"
)

# Check for mcp_call in output
for item in resp.output:
    if item.get("type") == "mcp_call":
        print(f"Tool: {item['name']}")
        print(f"Args: {item['arguments']}")
        print(f"Output: {item['output']}")
```

## Troubleshooting

### "401 Unauthorized"
- Check `Authorization` header is set
- Verify token matches `MCP_API_KEY` in environment
- Ensure format is `Bearer <token>`

### "404 Unknown tool"
- Verify tool name matches exactly
- Check `allowed_tools` filter if used
- Call `list_tools` to see available tools

### "429 Too Many Requests"
- Rate limit exceeded (100/min default)
- Adjust limit in `http_server.py`
- Implement per-token limits

### "500 Internal Server Error"
- Check server logs for details
- Verify tool implementation doesn't throw
- Check external API connectivity

### Tools not appearing in OpenAI
- Verify `server_url` is publicly accessible
- Check HTTPS certificate is valid
- Test `/mcp` endpoint directly with curl
- Review OpenAI API logs

## Performance Tips

1. **Keep tool outputs small** (< 10KB)
2. **Use pagination** with cursors
3. **Cache tool definitions** (OpenAI caches `mcp_list_tools`)
4. **Add timeouts** to external API calls (10s max)
5. **Use connection pooling** for database/API calls
6. **Enable compression** in reverse proxy

## Next Steps

- [ ] Deploy to production environment
- [ ] Set up monitoring and alerts
- [ ] Implement OAuth 2.0 for better security
- [ ] Add more tools for your use case
- [ ] Create integration tests
- [ ] Document your custom tools
- [ ] Set up CI/CD pipeline
