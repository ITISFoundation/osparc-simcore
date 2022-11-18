from pydantic import BaseModel, ByteSize


class Resources(BaseModel):
    cpus: int
    ram: ByteSize
