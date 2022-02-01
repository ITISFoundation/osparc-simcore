from pydantic.class_validators import validator
from pydantic.fields import Field
from pydantic.types import SecretBytes
from settings_library.base import BaseCustomSettings


class SessionSettings(BaseCustomSettings):

    SESSION_SECRET_KEY: SecretBytes = Field(
        ...,
        description="Secret key to encrypt cookies",
        min_length=32,
        env=["SESSION_SECRET_KEY", "WEBSERVER_SESSION_SECRET_KEY"],
    )

    @validator("SESSION_SECRET_KEY", pre=True)
    @classmethod
    def truncate_session_key(cls, v):
        return v[:32]
