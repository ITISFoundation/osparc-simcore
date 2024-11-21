from pydantic import BaseModel, Field


class UsersGroup(BaseModel):
    gid: str = Field(..., coerce_numbers_to_str=True)
    label: str
    description: str | None = None


class Groups(BaseModel):
    me: UsersGroup
    organizations: list[UsersGroup] | None = []
    all_: UsersGroup = Field(..., alias="all")
