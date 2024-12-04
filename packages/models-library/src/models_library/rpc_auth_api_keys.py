from pydantic import BaseModel


class ApiKeyGet(BaseModel):
    api_key: str
    api_secret: str
