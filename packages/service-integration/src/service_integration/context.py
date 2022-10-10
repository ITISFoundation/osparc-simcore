"""
Application level settings which are pulled in and 
share with all subcommands.

These settings have a default value, can be passed
via environment variables and are overwritable via 
cli option.
"""

from pydantic import BaseSettings, Extra, Field, SecretStr


class IntegrationContext(BaseSettings):
    REGISTRY_NAME: str = Field(
        "", description="name of the registry to use for images, default is Docker Hub"
    )
    COMPOSE_VERSION: str = Field(
        "3.7", description="version of the docker-compose spec"
    )

    class Config:
        case_sensitive = False
        extra = Extra.forbid
        validate_all = True
        json_encoders = {SecretStr: lambda v: v.get_secret_value()}
