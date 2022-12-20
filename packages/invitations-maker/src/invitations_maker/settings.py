from pydantic import BaseSettings, Field, HttpUrl, SecretStr


class ApplicationSettings(BaseSettings):

    INVITATIONS_MAKER_SECRET_KEY: SecretStr = Field(
        ...,
        description="Secret key to generate invitations"
        'TIP: python3 -c "from cryptography.fernet import *; print(Fernet.generate_key())"',
        min_length=44,
    )

    INVITATIONS_MAKER_OSPARC_URL: HttpUrl = Field(..., description="Target platform")
