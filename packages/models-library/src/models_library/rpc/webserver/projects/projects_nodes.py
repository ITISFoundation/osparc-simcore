from pydantic import BaseModel


class ProjectNodeGet(BaseModel):
    key: str
    version: str
    label: str
