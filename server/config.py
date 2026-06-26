"""Application configuration loaded from .env file"""

from functools import lru_cache

from pydantic_settings import BaseSettings,SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    # External API key
    owm_api_key:str = Field(..., env="OWM_API_KEY")
    
    #MCP Server Authenctication 
    mcp_api_key:str = Field(..., env="MCP_API_KEY")

    #--Server---

    host:str = Field("0.0.0.0", env="HOST")
    port:int = Field(8000, env="PORT")
    log_level:str = Field("info", env="LOG_LEVEL")
    debug:bool = Field(False, env="DEBUG")
    

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()


