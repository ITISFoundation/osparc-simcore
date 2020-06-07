from typing import Optional

from fastapi import Depends, HTTPException, Security, status

from loguru import logger

from ....db.repositories.users import UsersRepository
from ....models.domain.users import User
from ....models.schemas.tokens import TokenData
from ....services.jwt import get_access_token_data
from ..database import get_repository

# Declaration of security scheme:
#   - Adds components.securitySchemes['APiKey'] to openapi.yaml
#   - callable with request as argument -> extracts token from Authentication header
#

from fastapi.security.api_key import APIKeyHeader

API_KEY_NAME = "Authorization"

api_key_scheme = APIKeyHeader(name=API_KEY_NAME, scheme_name="ApiKeyAuth")


async def get_current_user_id(
    access_token: str = Depends(api_key_scheme),
    users_repo: UsersRepository = Depends(get_repository(UsersRepository)),
) -> int:

    def _create_credentials_exception(msg: str):

        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=msg,
            headers={"WWW-Authenticate": "apiKey"},
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


async def get_active_user_id(
    current_user_id: User = Security(get_current_user_id, scopes=["read"])
) -> int:
    # FIXME: Adds read scope. rename properly and activate scopes
    return current_user_id
