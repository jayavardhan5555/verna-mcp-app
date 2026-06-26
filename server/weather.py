"""
Weather MCP Server - OpenWeatherMap API Integration
"""

from __future__ import annotations

import httpx
import logging
from typing import Annotated,Literal
from pydantic import BaseModel, Field
from mcp.server.fastmcp import FastMCP
from server.config import Settings


logger = logging.getLogger(__name__)


OWM_CURRENT_URL = "https://api.openweathermap.org/data/2.5/weather"
OWM_FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"
OWM_GEOCODE_URL = "https://api.openweathermap.org/geo/1.0/direct"


_http_client: httpx.AsyncClient | None = None

def get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient()
    return _http_client

async def close_http_client() -> None:
    global _http_client
    if _http_client is not None and not _http_client.is_closed:
        await _http_client.aclose()
        _http_client = None


#Pydantic response models

class CurrentWeather(BaseModel):
    city:str
    country:str
    temperature:float
    humidity:int = Field(description = "humidity percentage 1-100")
    description:str
    feels_like:float
    wind_speed:float
    temp_min:float
    temp_max:float
    units:str = Field(description = "unit system used: metric | imperial | standard")

class ForecastEntry(BaseModel):
    datetime:str
    temperature:float
    humidity:int = Field(description = "humidity percentage 1-100")
    description:str
    feels_like:float
    wind_speed:float

class WeatherForecast(BaseModel):
    city:str
    country:str
    units:str = Field(description = "unit system used: metric | imperial | standard")
    forecast:list[ForecastEntry]

class CityResult(BaseModel):
    name:str
    country:str
    state:str | None = None
    lat:float
    lon:float


unit_system = Literal["metric", "imperial", "standard"]

async def _owm_get(url:str, params:dict) -> dict:
    """Issue a GET requestto OWM and raise Valur error on API error"""
    client = get_http_client()
    try:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        raise ValueError(f"OWM API error: {e.response.status_code} - {e.response.text}") from e
    except httpx.TimeoutException as e:
        raise ValueError("OWM API timeout") from e
    except Exception as e:
        raise ValueError(f"OWM API error: {e}") from e


def _parse_current(data:dict, units:str) -> CurrentWeather:
    return CurrentWeather(
        city=data["name"],
        country=data["sys"]["country"],
        temperature=data["main"]["temp"],
        humidity=data["main"]["humidity"],
        description=data["weather"][0]["description"],
        feels_like=data["main"]["feels_like"],
        wind_speed=data["wind"]["speed"],
        temp_min=data["main"]["temp_min"],
        temp_max=data["main"]["temp_max"],
        units=units
    )

def _parse_forecast(data:dict, units:str) -> WeatherForecast:
    return WeatherForecast(
        city=data["city"]["name"],
        country=data["city"]["country"],
        units=units,
        forecast=[
            ForecastEntry(
                datetime=entry["dt_txt"],
                temperature=entry["main"]["temp"],
                humidity=entry["main"]["humidity"],
                description=entry["weather"][0]["description"],
                feels_like=entry["main"]["feels_like"],
                wind_speed=entry["wind"]["speed"]
            )
            for entry in data["list"]
        ]
    )

def register_tools(mcp:FastMCP, settings: Settings) -> None:
    """Register all weather tool on mcp"""

    owm_key = settings.owm_api_key

    #Tool 1 - Current weather by city name

    @mcp.tool()
    async def get_current_weather(city:Annotated[str, Field(description="City name")],units:unit_system ="metric") ->CurrentWeather:
        """
        Get current weather for a city
        """
        data = await _owm_get(OWM_CURRENT_URL, {"q": city, "appid": owm_key, "units": units})
        return _parse_current(data, units)

    #Tool 2 - multi day forecast by city name
    
    @mcp.tool()
    async def get_forecast(city:Annotated[str, Field(description="City name")],days:Annotated[int, Field(description="Number of days to forecast", ge=1, le=5)] = 5, units:unit_system ="metric") ->WeatherForecast:
        """
        Get multi-day weather forecast for a city
        """
        data = await _owm_get(OWM_FORECAST_URL, {"q": city, "appid": owm_key, "units": units})
        return _parse_forecast(data, units)

    #Tool 3 - Current weather by coordinates
    
    @mcp.tool()
    async def get_current_weather_by_coords(lat:Annotated[float, Field(description="Latitude")],lon:Annotated[float, Field(description="Longitude")],units:unit_system ="metric") ->CurrentWeather:
        """
        Get current weather for coordinates
        """
        data = await _owm_get(OWM_CURRENT_URL, {"lat": lat, "lon": lon, "appid": owm_key, "units": units})
        return _parse_current(data, units)

    #Tool 4- geo coding /city searcg
    @mcp.tool()
    async def search_Cities(
        query: Annotated[str, Field(description="City name to search for")],
        limit: Annotated[int, Field(description="Maximum number of results to return", ge=1, le=10)] = 5
    ):
        """
        Search for cities by name
        """
        data = await _owm_get(OWM_GEOCODE_URL, {"q": query, "appid": owm_key, "limit": limit})
        if not isinstance(data,list):
            return []
        return [
            CityResult(
                name=entry["name"],
                country=entry.get("country", ""),
                lat=entry["lat"],
                lon=entry["lon"],
                state=entry.get("state")
            )
            for entry in data
        ]

    