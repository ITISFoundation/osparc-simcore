from pydantic import BaseModel, Field, SecretStr


class ApiKey(BaseModel):
    api_key: str
    api_secret: SecretStr


class ApiKeyInDB(BaseModel):
    api_key: str
    api_secret: str

    id_: int = Field(0, alias="id")
    display_name: str
    user_id: int
    product_name: str

    class Config:
        orm_mode = True
