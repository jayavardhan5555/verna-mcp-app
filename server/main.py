import contextlib
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
import uvicorn
from mcp.server.fastmcp import FastMCP
import logging
import logging.config
from starlette.types import ASGIApp
from starlette.requests import Request
from starlette.responses import JSONResponse
from server.config import get_settings
from server.weather import close_http_client
from server.auth import APIKeyMiddleware
from starlette.routing import Mount,Route

### logging

def _configure_logging(level:str) -> None:
    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default"
            }
        },
        "root": {
            "level": level.upper(),
            "handlers": ["console"]
        }
    })

logger = logging.getLogger(__name__)

## Build the application

def create_app() -> ASGIApp:
    settings = get_settings()
    _configure_logging(settings.log_level)
    
    mcp = FastMCP("Verna Weather Gateway", stateless_http=True, json_response=True, instructions=(
        "Production MCP gateway for OpenWeatherMap API"
        "Tools: get_current_weather, get_weather_forecast, get_weather_by_coordinates, search_cities"
    ))
    from server.weather import register_tools
    register_tools(mcp, settings)

    @asynccontextmanager
    async def lifespan(_app: Starlette) -> AsyncIterator[None]:
        logger.info("Verna Weather Gateway starting...")
        async with contextlib.AsyncExitStack() as stack:
            await stack.enter_async_context(mcp.session_manager.run())
            try:
                yield
            finally:
                await close_http_client()
                logger.info("Verna Weather Gateway shutting down...")

    
    async def health(_request:Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "service": "verna-weather-gateway", "version": "1.0.0"})

    starlette_app = Starlette(
        routes=[
            Route("/health", health, methods=["GET"]),
            Mount("/", app = mcp.streamable_http_app())
        ],
        lifespan=lifespan
    )

    app_with_cors = CORSMiddleware(
        starlette_app,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "OPTIONS", "DELETE"],
        allow_headers=["*"],
        expose_headers=["Mcp-Session-Id"]
    )

    return APIKeyMiddleware(app_with_cors, api_key=settings.mcp_api_key)

app = create_app()

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run("server.main:app", host=settings.host, port=settings.port, reload=settings.reload,access_log=True, log_level=settings.log_level.lower())
