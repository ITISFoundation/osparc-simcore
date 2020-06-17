## https://pydantic-docs.helpmanual.io/usage/settings/#dotenv-env-support
import os
from pathlib import Path

from pydantic import BaseSettings, SecretStr

env_path = Path(".env-ignore")

env_path.write_text(
    """
# ignore comment
ENVIRONMENT="production"
REDIS_ADDRESS=localhost:6379
MEANING_OF_LIFE=4000000
MY_VAR='Hello world'
POSTGRES_USER=test
POSTGRES_PASSWORD=test
POSTGRES_DB=test
"""
)


os.environ["MEANING_OF_LIFE"] = "42"


class PostgresSettings(BaseSettings):
    user: str
    password: SecretStr
    db: str

    class Config:
        env_file = env_path
        env_prefix = "POSTGRES_"


class Settings(BaseSettings):
    environment: str
    meaning_of_life: int = 33

    pg = PostgresSettings()

    class Config:
        env_file = env_path


settings = Settings()

print(settings.json())
assert settings.meaning_of_life == 42
assert settings.environment == "production"
assert settings.pg.password.get_secret_value() == "test"
