from pydantic import BaseModel, ByteSize, NonNegativeInt


class Resources(BaseModel):
    cpus: NonNegativeInt
    ram: ByteSize
