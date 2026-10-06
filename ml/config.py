from functools import lru_cache
from typing import Literal
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class MLSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    APP_ENV: Literal['development', 'production'] = 'production'
    ML_API_KEY: str = ''
    MAX_UPLOAD_BYTES: int = Field(default=10 * 1024 * 1024, gt=0)
    MAX_IMAGE_PIXELS: int = Field(default=20_000_000, gt=0)

    @model_validator(mode='after')
    def service_secret(self):
        if self.APP_ENV == 'production' and len(self.ML_API_KEY) < 32:
            raise ValueError('Production inference requires a strong ML_API_KEY')
        return self


@lru_cache()
def get_settings():
    return MLSettings()
