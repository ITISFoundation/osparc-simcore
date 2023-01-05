from pydantic import BaseSettings, Field, HttpUrl, SecretStr


class BasicApplicationSettings(BaseSettings):

    INVITATIONS_MAKER_SECRET_KEY: SecretStr = Field(
        ...,
        description="Secret key to generate invitations"
        'TIP: python3 -c "from cryptography.fernet import *; print(Fernet.generate_key())"',
        min_length=44,
    )

    INVITATIONS_MAKER_OSPARC_URL: HttpUrl = Field(..., description="Target platform")


class ApplicationSettings(BasicApplicationSettings):
    """web app settings"""

    INVITATIONS_USERNAME: str = Field(
        ...,
        description="Username for HTTP Basic Auth. Required if started as a web app.",
        min_length=3,
    )
    INVITATIONS_PASSWORD: SecretStr = Field(
        ...,
        description="Password for HTTP Basic Auth. Required if started as a web app.",
        min_length=10,
    )
