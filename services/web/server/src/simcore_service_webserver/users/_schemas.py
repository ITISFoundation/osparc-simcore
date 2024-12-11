""" models for rest api schemas, i.e. those defined in openapi.json

"""


from models_library.users import UserID
from pydantic import BaseModel, Field
from servicelib.request_keys import RQT_USERID_KEY

from .._constants import RQ_PRODUCT_KEY


class UsersRequestContext(BaseModel):
    user_id: UserID = Field(..., alias=RQT_USERID_KEY)  # type: ignore[literal-required]
    product_name: str = Field(..., alias=RQ_PRODUCT_KEY)  # type: ignore[literal-required]
