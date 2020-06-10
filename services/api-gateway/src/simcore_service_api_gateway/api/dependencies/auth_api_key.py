from typing import Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security.api_key import APIKeyHeader
from loguru import logger

from ...db.repositories.users import UsersRepository
from ...models.schemas.tokens import TokenData
from ...services.jwt import get_access_token_data
from .database import get_repository

# Declaration of security scheme:
#   - Adds components.securitySchemes['APiKey'] to openapi.yaml
#   - callable with request as argument -> extracts token from Authentication header
#


API_KEY_NAME = "APIKey"
api_key_scheme = APIKeyHeader(name=API_KEY_NAME)


async def get_current_user_id(
    access_token: str = Security(api_key_scheme),
    users_repo: UsersRepository = Depends(get_repository(UsersRepository)),
) -> int:
    def _create_credentials_exception(msg: str):

        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=msg,
            headers={"WWW-Authenticate": API_KEY_NAME},
        )

    # decodes and validates jwt-based access token
    token_data: Optional[TokenData] = get_access_token_data(access_token)
    if token_data is None:
        raise _create_credentials_exception("Could not validate credentials")

    # identify user
    identified = await users_repo.any_user_with_id(token_data.user_id)
    if not identified:
        raise _create_credentials_exception("Could not validate credentials")

    return token_data.user_id


get_active_user_id = get_current_user_id
