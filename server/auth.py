"""API Key authenctication middleware for MCP endpoints

All requests to paths starting with /mcp must include a valid ``X-API-KEY`` header
with the correct API key value.
"""

import json
import secrets

from starlette.types import ASGIApp, Receive, Scope, Send

_PROTECTED_PREFIX = "/mcp"
_HEADER_NAME = b"x-api-key"

class APIKeyMiddleware:
    def __init__(self, app: ASGIApp, api_key: str):
        if not api_key:
            raise ValueError("API key is required")
        self.app = app
        self.api_key = api_key

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            path:str = scope.get("path", "")
            method:str = scope.get("method", "")
            
            if path.startswith(_PROTECTED_PREFIX) and method != "OPTIONS":
                headers:dict[bytes,bytes] = dict(scope.get("headers", []))
                provided = headers.get(_HEADER_NAME, b"").decode("utf-8", errors="replace")

                if not secrets.compare_digest(provided,self.api_key):
                    await _send_401(send)
                    return
                    
        await self.app(scope, receive, send)
    
async def _send_401(send:Send) -> None:
    body = json.dumps(
        {
            "error": "Unauthorized", "detail": "Invalid or misisng X-API-Key header"
        }
    ).encode()

    await send(
        {
            "type": "http.response.start",
            "status": 401,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii"))
            ]
        }
    )
    
    await send(
        {
            "type": "http.response.body",
            "body": body
        }
    )
                