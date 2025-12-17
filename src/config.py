#!/usr/bin/env python3

from pydantic import BaseSettings

class Settings(BaseSettings):
    WEBPOSTO_API_URL: str = "https://web.qualityautomacao.com.br/INTEGRACAO"
    WEBPOSTO_API_KEY: str

    class Config:
        env_file = ".env"

settings = Settings()
