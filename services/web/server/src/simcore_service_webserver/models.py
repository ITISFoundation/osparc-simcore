from typing import Annotated

from models_library.products import ProductName
from models_library.rest_base import RequestParameters
from models_library.users import UserID
from pydantic import ConfigDict, Field
from servicelib.request_keys import RQT_USERID_KEY

from .constants import RQ_PRODUCT_KEY


class AuthenticatedRequestContext(RequestParameters):
    """Fields expected in the request context for authenticated endpoints"""

    user_id: Annotated[UserID, Field(alias=RQT_USERID_KEY)]
    product_name: Annotated[ProductName, Field(alias=RQ_PRODUCT_KEY)]

    model_config = ConfigDict(
        frozen=True  # prevents modifications after middlewares creates this model
    )
