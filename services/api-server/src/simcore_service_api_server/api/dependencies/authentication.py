from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from ...db.repositories.api_keys import ApiKeysRepository, User
from ...db.repositories.users import UsersRepository
from .database import get_repository

# SEE https://swagger.io/docs/specification/authentication/basic-authentication/
basic_scheme = HTTPBasic()


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
    credentials: HTTPBasicCredentials = Security(basic_scheme),
) -> User:
    user: User | None = await apikeys_repo.get_user(
        api_key=credentials.username, api_secret=credentials.password
    )
    if user is None:
        exc = _create_exception()
        raise exc
    return user


async def get_active_user_email(
    user: Annotated[User, Depends(get_current_user)],
    users_repo: Annotated[UsersRepository, Depends(get_repository(UsersRepository))],
) -> str:
    email = await users_repo.get_email_from_user_id(user.user_id)
    if not email:
        exc = _create_exception()
        raise exc
    return email
