from pydantic import BaseModel


class SessionData(BaseModel):
    username: str | None = None
