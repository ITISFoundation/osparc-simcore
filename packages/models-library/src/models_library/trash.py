from pydantic import BaseModel, Field


class RemoveQueryParams(BaseModel):
    force: bool = Field(
        default=False, description="Force removal (even if resource is active)"
    )
