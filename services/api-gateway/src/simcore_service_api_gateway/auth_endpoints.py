import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from .auth_security import authenticate_user, create_access_token
from .schemas import Token, UserInDB
from .utils.helpers import json_dumps

log = logging.getLogger(__name__)


# Authorization SERVER -------------------------------------
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


router = APIRouter()


@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):

    print("Form Request", "-" * 20)
    for (
        attr
    ) in "grant_type   username    password    scopes    client_id    client_secret".split():
        print("-", attr, ":", getattr(form_data, attr))
    print("-" * 20)

    user: Optional[UserInDB] = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    # TODO: grant requested scopes OR NOT!

    access_token = create_access_token(
        subject={"sub": user.username, "scopes": form_data.scopes}
    )
    #
    resp_data = {"access_token": access_token, "token_type": "bearer"}

    print("{:-^30}".format("/token response"))
    print(json_dumps(resp_data))
    print("-" * 30)
    return resp_data
