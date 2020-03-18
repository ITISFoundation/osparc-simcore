from pydantic import BaseSettings, PostgresDsn, Field #pylint: disable=no-name-in-module


class Settings(BaseSettings):
    # DOCKER
    boot_mode: bool = Field(..., env="SC_BOOT_MODE")

    # LOGGING
    loglevel: str

    # POSTGRES
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    postgres_dsn: PostgresDsn  # TODO: compose with above

    # WEBSERVER
    webserver_host: str = "webserver"
    webserver_port: int = 8080

    # SERVICE SERVER (see : https://www.uvicorn.org/settings/)
    host: str = "localhost"  # "0.0.0.0" if is_containerized else "127.0.0.1",
    port: int = 8000

    class Config:
        env_prefix=""
        case_sensitive = False
