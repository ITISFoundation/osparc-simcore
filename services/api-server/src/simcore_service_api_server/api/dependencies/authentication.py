from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, PositiveInt

from ...db.repositories.api_keys import ApiKeysRepository, UserAndProduct
from ...db.repositories.users import UsersRepository
from .database import get_repository

# SEE https://swagger.io/docs/specification/authentication/basic-authentication/
basic_scheme = HTTPBasic()


class User(BaseModel):
    user_id: PositiveInt
    product_id: PositiveInt
    email: str


def _create_exception() -> HTTPException:
    _unauthorized_headers = {
        "WWW-Authenticate": f'Basic realm="{basic_scheme.realm}"'
        if basic_scheme.realm
        else "Basic"
    }
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API credentials",
        headers=_unauthorized_headers,
    )


async def get_current_user(
    apikeys_repo: Annotated[
        ApiKeysRepository, Depends(get_repository(ApiKeysRepository))
    ],
    users_repo: Annotated[UsersRepository, Depends(get_repository(UsersRepository))],
    credentials: HTTPBasicCredentials = Security(basic_scheme),
) -> User:
    user_and_product: UserAndProduct | None = await apikeys_repo.get_user(
        api_key=credentials.username, api_secret=credentials.password
    )
    if user_and_product is None:
        exc = _create_exception()
        raise exc
    email = await users_repo.get_email_from_user_id(user_and_product[0])
    if not email:
        exc = _create_exception()
        raise exc
    return User(
        user_id=user_and_product[0], product_id=user_and_product[1], email=email
    )


async def get_current_user_id(
    user: Annotated[User, Depends(get_current_user)],
) -> PositiveInt:
    return user.user_id


async def get_active_user_email(
    user: Annotated[User, Depends(get_current_user)],
) -> str:
    return user.email
