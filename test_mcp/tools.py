"""
Tool implementations for the MCP server.
These tools can call your actual API or implement mock logic.
"""
import os
import io
from typing import Any, Dict
import httpx
from datetime import datetime
from supabase import create_client, Client
from openai import OpenAI
from .config import settings


# Configuration - can be moved to config.py
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
API_KEY = os.getenv("API_KEY", "")


async def call_api(method: str, path: str, **kwargs) -> Dict[str, Any]:
    """
    Helper function to call an external API.
    Replace this with your actual API calls or remove if using mock data.
    """
    headers = {}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        url = f"{API_BASE_URL}{path}"
        response = await client.request(method, url, headers=headers, **kwargs)
        response.raise_for_status()
        return response.json()


def get_supabase_client() -> Client:
    """
    Get a Supabase client instance.
    """
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in environment variables")

    return create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)


async def search_items_tool(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Search for items based on a query.
    
    This is a mock implementation. Replace with actual API calls:
    - Call your database
    - Call an external search API
    - Use the call_api helper above
    """
    query = arguments.get("query", "")
    limit = arguments.get("limit", 10)
    cursor = arguments.get("cursor")
    
    # Mock implementation - replace with real logic
    mock_items = [
        {
            "id": "item_001",
            "title": f"Result for '{query}' - Item 1",
            "summary": "This is a mock search result. Replace with real data.",
            "score": 0.95
        },
        {
            "id": "item_002",
            "title": f"Result for '{query}' - Item 2",
            "summary": "Another mock result from the search.",
            "score": 0.87
        },
        {
            "id": "item_003",
            "title": f"Result for '{query}' - Item 3",
            "summary": "Third mock result demonstrating pagination.",
            "score": 0.76
        }
    ]
    
    # Apply limit
    items = mock_items[:limit]
    
    # Mock pagination cursor
    next_cursor = "cursor_next_page" if len(mock_items) > limit else None
    
    return {
        "items": items,
        "nextCursor": next_cursor,
        "total": len(mock_items)
    }
    
    # Example of calling a real API:
    # try:
    #     params = {"q": query, "limit": limit}
    #     if cursor:
    #         params["cursor"] = cursor
    #     
    #     data = await call_api("GET", "/search", params=params)
    #     return {
    #         "items": data.get("items", []),
    #         "nextCursor": data.get("nextCursor"),
    #         "total": data.get("total", 0)
    #     }
    # except Exception as e:
    #     return {
    #         "error": str(e),
    #         "items": [],
    #         "nextCursor": None
    #     }


async def get_item_tool(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Retrieve a single item by ID.
    
    This is a mock implementation. Replace with actual API calls.
    """
    item_id = arguments.get("id", "")
    
    # Mock implementation - replace with real logic
    mock_item = {
        "id": item_id,
        "title": f"Item {item_id}",
        "body": "This is the detailed content of the item. Replace with real data from your database or API.",
        "createdAt": "2025-10-08T08:00:00Z",
        "updatedAt": "2025-10-08T08:30:00Z",
        "url": f"https://example.com/items/{item_id}",
        "metadata": {
            "author": "Test Author",
            "tags": ["test", "mock", "example"]
        }
    }
    
    return mock_item
    
    # Example of calling a real API:
    # try:
    #     data = await call_api("GET", f"/items/{item_id}")
    #     return data
    # except httpx.HTTPStatusError as e:
    #     if e.response.status_code == 404:
    #         return {"error": f"Item '{item_id}' not found"}
    #     return {"error": f"API error: {e.response.status_code}"}
    # except Exception as e:
    #     return {"error": str(e)}


async def health_tool(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check the health of the server and any dependencies.
    """
    health_status = {
        "status": "healthy",
        "server": "test-mcp-server",
        "version": "0.1.0",
        "timestamp": "2025-10-08T08:43:00Z"
    }

    # Optional: Check upstream API health
    # try:
    #     await call_api("GET", "/health")
    #     health_status["upstream_api"] = "healthy"
    # except Exception as e:
    #     health_status["upstream_api"] = "unhealthy"
    #     health_status["upstream_error"] = str(e)

    return health_status


async def save_documentation_tool(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Save API documentation to Supabase and upload to OpenAI vector store.

    Arguments:
        api_name: Name of the API (e.g., "Stripe", "OpenAI")
        endpoint_path: The endpoint path (e.g., "/v1/chat/completions")
        http_method: HTTP method (GET, POST, PUT, DELETE, etc.)
        category: Short category string
        title: Human-readable title
        documentation: The documentation text
        short_description: Short description for vector store semantic search
        tags: Optional array of tags
        version: Optional API version
        examples: Optional JSON with code examples
        parameters: Optional JSON describing parameters
        source_url: Optional URL to original documentation
    """
    try:
        supabase = get_supabase_client()

        # Prepare the data for Supabase
        data = {
            "api_name": arguments.get("api_name"),
            "endpoint_path": arguments.get("endpoint_path"),
            "http_method": arguments.get("http_method"),
            "category": arguments.get("category"),
            "title": arguments.get("title"),
            "documentation": arguments.get("documentation"),
            "short_description": arguments.get("short_description"),
            "tags": arguments.get("tags"),
            "version": arguments.get("version"),
            "examples": arguments.get("examples"),
            "parameters": arguments.get("parameters"),
            "source_url": arguments.get("source_url"),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }

        # Remove None values
        data = {k: v for k, v in data.items() if v is not None}

        # Insert into Supabase
        result = supabase.table("api_documentation").insert(data).execute()

        doc_id = result.data[0]["id"] if result.data else None

        # Upload to OpenAI vector store if short_description is provided
        vector_store_file_id = None
        if arguments.get("short_description") and settings.OPENAI_API_KEY and settings.OPENAI_VECTOR_STORE_ID:
            try:
                openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)

                # Create a file from the short description
                file_content = arguments.get("short_description").encode('utf-8')
                file_obj = io.BytesIO(file_content)
                file_obj.name = f"doc_{doc_id}.txt"

                # Upload file to OpenAI
                file_response = openai_client.files.create(
                    file=file_obj,
                    purpose="assistants"
                )

                # Add file to vector store with metadata
                vector_store_response = openai_client.beta.vector_stores.files.create(
                    vector_store_id=settings.OPENAI_VECTOR_STORE_ID,
                    file_id=file_response.id,
                    attributes={
                        "supabase_id": str(doc_id),
                        "api_name": arguments.get("api_name"),
                        "endpoint_path": arguments.get("endpoint_path", ""),
                        "category": arguments.get("category", "")
                    }
                )

                vector_store_file_id = vector_store_response.id

            except Exception as e:
                # Don't fail the whole operation if vector store upload fails
                print(f"Warning: Failed to upload to vector store: {str(e)}")

        return {
            "success": True,
            "id": doc_id,
            "vector_store_file_id": vector_store_file_id,
            "message": "Documentation saved successfully" + (" and uploaded to vector store" if vector_store_file_id else "")
        }

    except ValueError as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Supabase configuration error"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to save documentation"
        }
