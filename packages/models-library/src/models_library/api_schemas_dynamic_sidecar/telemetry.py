from pydantic import BaseModel, Field, NonNegativeInt


class DiskUsage(BaseModel):
    total: NonNegativeInt
    used: NonNegativeInt
    free: NonNegativeInt
    percent: float = Field(gte=0.0, lte=1.0)
