""" This submodule includes responsibilities from authorization server

 +--------+                               +---------------+
 |        |--(A)- Authorization Request ->|   Resource    |
 |        |                               |     Owner     | Authorization request
 |        |<-(B)-- Authorization Grant ---|               |
 |        |                               +---------------+
 |        |
 |        |                               +---------------+
 |        |--(C)-- Authorization Grant -->| Authorization |
 | Client |                               |     Server    | Token request
 |        |<-(D)----- Access Token -------|               |
 |        |                               +---------------+
 |        |
 |        |                               +---------------+
 |        |--(E)----- Access Token ------>|    Resource   |
 |        |                               |     Server    |
 |        |<-(F)--- Protected Resource ---|               |
 +--------+                               +---------------+

                 Figure 1: Abstract Protocol Flow

SEE
    - https://oauth.net/2/
    - https://tools.ietf.org/html/rfc6749
"""
# TODO: this module shall delegate the auth functionality to a separate service

import logging
from typing import Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import OAuth2PasswordBearer, SecurityScopes

from . import crud_users as crud
from .__version__ import api_vtag
from .api_dependencies_db import SAConnection, get_db_connection
from .auth_security import get_access_token_data
from .schemas import TokenData, User, UserInDB

log = logging.getLogger(__name__)


# Declaration of security scheme:
#   - Adds components.securitySchemes['OAuth2PasswordBearer'] to openapi.yaml
#   - callable with request as argument -> extracts token from Authentication header
#
# TODO: check organization of scopes in other APIs
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{api_vtag}/token",
    scopes={"read": "Read-only access", "write": "Write access"},
)


async def get_current_user(
    security_scopes: SecurityScopes,
    access_token: str = Depends(oauth2_scheme),
    conn: SAConnection = Depends(get_db_connection),
) -> User:
    """
        access_token: extracted access_token from request header
        security_scopes: iterable with all REQUIRED scopes to run operation
    """

    def _create_credentials_exception(msg: str):
        authenticate_value = "Bearer"
        if security_scopes.scopes:
            authenticate_value += f' scope="{security_scopes.scope_str}"'

        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=msg,
            headers={"WWW-Authenticate": authenticate_value},
        )

    # decodes and validates jwt-based access token
    token_data: Optional[TokenData] = get_access_token_data(access_token)
    if token_data is None:
        raise _create_credentials_exception("Could not validate credentials")

    # identify user
    # user: Optional[UserInDB] = crud.get_user(username=token_data.username)
    user: Optional[User] = await crud.get_user_by_id(conn, int(token_data.username))
    if user is None:
        raise _create_credentials_exception("Could not validate credentials")

    # Checks whether user has ALL required scopes for this call
    for required_scope in security_scopes.scopes:
        if required_scope not in token_data.scopes:
            log.debug(
                "Access denied. Client is missing required scope '%s' ", required_scope
            )
            raise _create_credentials_exception(
                "Missing required scope for this operation"
            )

    return user


async def get_current_active_user(
    current_user: User = Security(get_current_user, scopes=["read"])
):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
