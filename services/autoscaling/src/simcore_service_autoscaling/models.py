from pydantic import BaseModel, ByteSize, NonNegativeFloat


class Resources(BaseModel):
    cpus: NonNegativeFloat
    ram: ByteSize
