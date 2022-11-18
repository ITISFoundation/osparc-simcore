from pydantic import BaseModel, ByteSize, PositiveInt


class Resources(BaseModel):
    cpus: PositiveInt
    ram: ByteSize
