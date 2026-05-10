import logging
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str = ""
    model_name: str = "gpt-4o-mini"
    temperature: float = 0.0
    openai_api_base: str | None = None
    port: int = 8501

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_llm():
    from langchain_openai import ChatOpenAI

    settings = get_settings()
    kwargs = {
        "model": settings.model_name,
        "temperature": settings.temperature,
        "api_key": settings.openai_api_key,
    }
    if settings.openai_api_base:
        kwargs["base_url"] = settings.openai_api_base
    return ChatOpenAI(**kwargs)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
