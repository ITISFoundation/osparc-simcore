from pydantic import BaseModel, ConfigDict, Field


class Position(BaseModel):
    x: int = Field(..., description="The x position", examples=[["12"]])
    y: int = Field(..., description="The y position", examples=[["15"]])

    model_config = ConfigDict(extra="forbid")
