from models_library.rest_base import RequestParameters
from models_library.users import UserID
from pydantic import Field
from servicelib.request_keys import RQT_USERID_KEY

from ._constants import RQ_PRODUCT_KEY


class RequestContext(RequestParameters):
    user_id: UserID = Field(..., alias=RQT_USERID_KEY)  # type: ignore[literal-required]
    product_name: str = Field(..., alias=RQ_PRODUCT_KEY)  # type: ignore[literal-required]
