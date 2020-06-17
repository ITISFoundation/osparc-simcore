from pydantic import BaseModel, EmailStr, Field

from simcore_postgres_database.models.users import UserRole, UserStatus

from .groups import Groups


class UserBase(BaseModel):
    first_name: str
    last_name: str


class User(UserBase):
    login: EmailStr
    role: str
    groups: Groups
    gravatar_id: str


class UserInDB(BaseModel):
    id_: int = Field(0, alias="id")
    name: str
    email: str
    password_hash: str
    primary_gid: int
    status: UserStatus
    role: UserRole

    # TODO: connect name <-> first_name, last_name

    class Config:
        orm_mode = True
