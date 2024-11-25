from pydantic import BaseModel, ConfigDict, Field


class AccessRights(BaseModel):
    read: bool = Field(..., description="has read access")
    write: bool = Field(..., description="has write access")
    delete: bool = Field(..., description="has deletion rights")

    model_config = ConfigDict(extra="forbid")
