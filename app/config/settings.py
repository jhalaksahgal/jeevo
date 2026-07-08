from pydantic_settings import BaseSettings
from typing import Optional
class Settings(BaseSettings):
    APP_NAME: str = "Jeevo Health Platform"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False
    WHATSAPP_API_URL: str
    WHATSAPP_PHONE_NUMBER_ID: str
    WHATSAPP_ACCESS_TOKEN: str
    WHATSAPP_VERIFY_TOKEN: str
    WEBHOOK_VERIFY_TOKEN: str
    DATABASE_URL: str
    DATABASE_ECHO: bool = False
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_TTL: int = 3600
    SESSION_EXPIRE_MINUTES: int = 60
    USE_GROQ: bool = True
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_VISION_MODEL: str = "llama-3.2-90b-vision-preview"
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_VISION_MODEL: str = "gpt-4o-mini"
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.5-flash"
    ELEVENLABS_API_KEY: Optional[str] = None
    OPENWEATHER_API_KEY: Optional[str] = None
    GOOGLE_MAPS_API_KEY: Optional[str] = None
    GOOGLE_WEATHER_API_URL: Optional[str] = None
    GOOGLE_AQI_API_URL: Optional[str] = None
    class Config:
        env_file = ".env"
        case_sensitive = True
settings = Settings()
