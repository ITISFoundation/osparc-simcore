from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from models_library.emails import LowerCaseEmailStr
from models_library.products import ProductName
from pydantic import BaseModel, PositiveInt

from ...db.repositories.api_keys import ApiKeysRepository, UserAndProductTuple
from ...db.repositories.users import UsersRepository
from .database import get_repository

# SEE https://swagger.io/docs/specification/authentication/basic-authentication/
basic_scheme = HTTPBasic()


class Identity(BaseModel):
    user_id: PositiveInt
    product_name: ProductName
    email: LowerCaseEmailStr


def _create_exception() -> HTTPException:
    _unauthorized_headers = {
        "WWW-Authenticate": (
            f'Basic realm="{basic_scheme.realm}"' if basic_scheme.realm else "Basic"
        )
    }
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API credentials",
        headers=_unauthorized_headers,
    )


async def get_current_identity(
    apikeys_repo: Annotated[
        ApiKeysRepository, Depends(get_repository(ApiKeysRepository))
    ],
    users_repo: Annotated[UsersRepository, Depends(get_repository(UsersRepository))],
    credentials: HTTPBasicCredentials = Security(basic_scheme),
) -> Identity:
    user_and_product: UserAndProductTuple | None = await apikeys_repo.get_user(
        api_key=credentials.username, api_secret=credentials.password
    )
    if user_and_product is None:
        exc = _create_exception()
        raise exc
    email = await users_repo.get_active_user_email(user_id=user_and_product.user_id)
    if not email:
        exc = _create_exception()
        raise exc
    return Identity(
        user_id=user_and_product.user_id,
        product_name=user_and_product.product_name,
        email=email,
    )


async def get_current_user_id(
    identity: Annotated[Identity, Depends(get_current_identity)],
) -> PositiveInt:
    return identity.user_id


async def get_product_name(
    identity: Annotated[Identity, Depends(get_current_identity)],
) -> ProductName:
    return identity.product_name


async def get_active_user_email(
    identity: Annotated[Identity, Depends(get_current_identity)],
) -> LowerCaseEmailStr:
    return identity.email
