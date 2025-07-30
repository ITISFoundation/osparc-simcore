from typing import Annotated, TypeAlias

from models_library.products import ProductName
from models_library.rest_base import RequestParameters
from models_library.users import UserID
from pydantic import ConfigDict, Field
from pydantic_extra_types.phone_numbers import PhoneNumberValidator
from servicelib.request_keys import RQT_USERID_KEY
from servicelib.rest_constants import X_CLIENT_SESSION_ID_HEADER

from .constants import RQ_PRODUCT_KEY

PhoneNumberStr: TypeAlias = Annotated[
    # NOTE: validator require installing `phonenumbers``
    str,
    PhoneNumberValidator(number_format="E164"),
]


class AuthenticatedRequestContext(RequestParameters):
    """Fields expected in the request context for authenticated endpoints"""

    user_id: Annotated[UserID, Field(alias=RQT_USERID_KEY)]
    product_name: Annotated[ProductName, Field(alias=RQ_PRODUCT_KEY)]

    model_config = ConfigDict(
        frozen=True  # prevents modifications after middlewares creates this model
    )


class ClientSessionHeaderParams(RequestParameters):
    """Header parameters for client session tracking in collaborative features."""

    client_session_id: str | None = Field(
        default=None,
        alias=X_CLIENT_SESSION_ID_HEADER,
        description="Client session identifier for collaborative features",
    )

    model_config = ConfigDict(
        populate_by_name=True,
        extra="forbid",
    )
