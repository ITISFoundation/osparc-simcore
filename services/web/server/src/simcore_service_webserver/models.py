from typing import Annotated, TypeAlias

from models_library.products import ProductName
from models_library.rest_base import RequestParameters
from models_library.users import UserID
from pydantic import ConfigDict, Field, StringConstraints
from pydantic_extra_types.phone_numbers import PhoneNumberValidator
from servicelib.request_keys import RQT_USERID_KEY
from servicelib.rest_constants import X_CLIENT_SESSION_ID_HEADER

from .constants import RQ_PRODUCT_KEY

PhoneNumberStr: TypeAlias = Annotated[
    # NOTE: validator require installing `phonenumbers``
    str,
    PhoneNumberValidator(number_format="E164"),
]


ClientSessionID: TypeAlias = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=36,
        max_length=36,
        pattern=r"^[0-9a-fA-F\-]{36}$",  # UUID format
        strict=True,
    ),
]


class AuthenticatedRequestContext(RequestParameters):
    """Fields expected in the request context for authenticated endpoints"""

    user_id: Annotated[UserID, Field(alias=RQT_USERID_KEY)]
    product_name: Annotated[ProductName, Field(alias=RQ_PRODUCT_KEY)]

    model_config = ConfigDict(
        frozen=True  # prevents modifications after middlewares creates this model
    )


assert X_CLIENT_SESSION_ID_HEADER


class ClientSessionHeaderParams(RequestParameters):
    """Header parameters for client session tracking in collaborative features."""

    client_session_id: ClientSessionID | None = Field(
        default=None,
        alias="X-Client-Session-Id",  # X_CLIENT_SESSION_ID_HEADER,
        description="Client session identifier for collaborative features (UUID string)",
    )

    model_config = ConfigDict(
        validate_by_name=True,
    )
