from pydantic import BaseModel


class ZipTask(BaseModel):
    msg: str
