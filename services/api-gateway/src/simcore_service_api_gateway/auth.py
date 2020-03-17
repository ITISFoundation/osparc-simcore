import logging
from typing import Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import OAuth2PasswordBearer, SecurityScopes

from . import crud_users as crud
from .auth_security import get_access_token_data
from .schemas import TokenData, User, UserInDB


log = logging.getLogger(__name__)


# Resource SERVER ----------------------------------------------
#
#  +--------+                               +---------------+
#  |        |--(A)- Authorization Request ->|   Resource    |
#  |        |                               |     Owner     | Authorization request
#  |        |<-(B)-- Authorization Grant ---|               |
#  |        |                               +---------------+
#  |        |
#  |        |                               +---------------+
#  |        |--(C)-- Authorization Grant -->| Authorization |
#  | Client |                               |     Server    | Token request
#  |        |<-(D)----- Access Token -------|               |
#  |        |                               +---------------+
#  |        |
#  |        |                               +---------------+
#  |        |--(E)----- Access Token ------>|    Resource   |
#  |        |                               |     Server    |
#  |        |<-(F)--- Protected Resource ---|               |
#  +--------+                               +---------------+
#
#                  Figure 1: Abstract Protocol Flow


# callable with request as argument -> extracts token from Authentication header
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/token",
    scopes={
        "me": "Read information about the current user.",
        "projects": "Read projects.",
        "you": "Some other scope",
    },
)


async def get_current_user(
    security_scopes: SecurityScopes, access_token: str = Depends(oauth2_scheme)
) -> User:
    # TODO: SecurityScopes dependnecy?? ????
    #
    # security_scopes is FILLED with dependant scopes. Therefore it will
    # be filled differently depending who is calling it
    if security_scopes.scopes:
        authenticate_value = f'Bearer scope="{security_scopes.scope_str}"'
    else:
        authenticate_value = f"Bearer"

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": authenticate_value},
    )

    # validates and decode jwt-based access token
    token_data: Optional[TokenData] = get_access_token_data(access_token)
    if token_data is None:
        raise credentials_exception

    # identify user
    user: Optional[UserInDB] = crud.get_user(username=token_data.username)
    if user is None:
        raise credentials_exception

    # validate scope
    for scope in security_scopes.scopes:
        if scope not in token_data.scopes:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not enough permissions",
                headers={"WWW-Authenticate": authenticate_value},
            )
    # auto-converst into User??
    return user


async def get_current_active_user(
    current_user: User = Security(get_current_user, scopes=["me"])
):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
