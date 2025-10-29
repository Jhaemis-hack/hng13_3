from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    countries_api_url : str
    exchange_rate_url : str
    database_url: str

    model_config = SettingsConfigDict(env_file=".env")