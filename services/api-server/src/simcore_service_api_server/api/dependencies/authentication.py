from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from ...db.repositories.api_keys import ApiKeysRepository
from ...db.repositories.users import UsersRepository
from .database import get_repository

# SEE https://swagger.io/docs/specification/authentication/basic-authentication/
basic_scheme = HTTPBasic()


def _create_exception():
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


async def get_current_user_id(
    credentials: HTTPBasicCredentials = Security(basic_scheme),
    apikeys_repo: ApiKeysRepository = Depends(get_repository(ApiKeysRepository)),
) -> int:
    user_id = await apikeys_repo.get_user_id(
        api_key=credentials.username, api_secret=credentials.password
    )
    if not user_id:
        raise _create_exception()
    return user_id


async def get_active_user_email(
    user_id: int = Depends(get_current_user_id),
    users_repo: UsersRepository = Depends(get_repository(UsersRepository)),
) -> str:
    email = await users_repo.get_email_from_user_id(user_id)
    if not email:
        raise _create_exception()
    return email


# alias
get_active_user_id = get_current_user_id
