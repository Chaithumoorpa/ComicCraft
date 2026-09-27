from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    gemini_api_key: str = ""
    hf_token: str = ""

    # Current Gemini model names are configurable so the project does not
    # depend on model IDs hard-coded in the original documentation.
    gemini_outline_model: str = "gemini-3.8-flash"
    gemini_story_model: str = "gemini-3.1-pro-preview"
    # Optional: used when the models above hit their quota (HTTP 429).
    gemini_fallback_model: str = ""

    image_provider: str = "diffusers"  # diffusers | placeholder
    image_model_id: str = "stable-diffusion-v1-5/stable-diffusion-v1-5"
    image_steps: int = 20
    image_width: int = 512
    image_height: int = 512
    seed: int = 42

    app_host: str = "127.0.0.1"
    app_port: int = 8000
    debug: bool = True

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

@lru_cache
def get_settings() -> Settings:
    return Settings()
