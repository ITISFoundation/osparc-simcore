from pydantic import BaseModel, Field, SecretStr


class ApiKey(BaseModel):
    api_key: str
    api_secret: SecretStr


class ApiKeyInDB(ApiKey):
    id_: int = Field(0, alias="id")
    display_name: str
    user_id: int

    class Config:
        orm_mode=True
