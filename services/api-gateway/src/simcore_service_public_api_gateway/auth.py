#
# FROM https://fastapi.tiangolo.com/advanced/security/oauth2-scopes/
#

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


from pathlib import Path
from typing import List, Optional

from fastapi import Depends, HTTPException, Security, status, APIRouter
from fastapi.security import (
    OAuth2PasswordBearer,
    OAuth2PasswordRequestForm,
    SecurityScopes,
)


from .schemas import Token, TokenData, User, UserInDB, ValidationError

import logging
log = logging.getLogger(__name__)

from .auth_security import authenticate_user, create_access_token, get_access_token_data
from .utils.helpers import json_dumps
from . import crud_users as crud



# Authorization SERVER -------------------------------------
router = APIRouter()

@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):

    print("Form Request", "-" * 20)
    for (
        attr
    ) in "grant_type   username    password    scopes    client_id    client_secret".split():
        print("-", attr, ":", getattr(form_data, attr))
    print("-" * 20)

    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    # TODO: grant requested scopes OR NOT!

    access_token = create_access_token(
        data={"sub": user.username, "scopes": form_data.scopes}
    )
    #
    resp_data = {"access_token": access_token, "token_type": "bearer"}

    print("{:-^30}".format("/token response"))
    print(json_dumps(resp_data))
    print("-" * 30)
    return resp_data


# Resource SERVER ----------------------------------------------

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
