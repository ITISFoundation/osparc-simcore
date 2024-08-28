from pydantic.v1 import BaseModel


# NOTE: for now only used to check if the user exists
class Profile(BaseModel):
    id: str
