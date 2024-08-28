from pydantic.v1 import BaseModel


class SessionData(BaseModel):
    username: str | None = None
