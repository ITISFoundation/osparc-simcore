import logging
from io import StringIO
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from .auth_security import authenticate_user, create_access_token
from .schemas import Token, UserInDB
from .utils.helpers import json_dumps

log = logging.getLogger(__name__)


router = APIRouter()

# TODO: has to be the same as in auth.oauth2_scheme
@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    - This entrypoint is part of the Authorization Server
    - Implements access point to obtain access-tokens

    |        |                               +---------------+
    |        |--(C)-- Authorization Grant -->| Authorization |
    | Client |                               |     Server    | Token request
    |        |<-(D)----- Access Token -------|               |
    |        |                               +---------------+

    """
    stream = StringIO()
    print("Form Request", "-" * 20, file=stream)
    for (
        attr
    ) in "grant_type username password scopes client_id client_secret".split():
        print("-", attr, ":", getattr(form_data, attr), file=stream)
    print("-" * 20, file=stream)
    log.debug(stream.getvalue())

    user: Optional[UserInDB] = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    # TODO: grant requested scopes OR NOT!

    access_token = create_access_token(
        subject={"sub": user.username, "scopes": form_data.scopes}
    )
    # TODO: THIS IS A STANDARD RESPOSE!
    resp_data = {"access_token": access_token, "token_type": "bearer"}

    stream = StringIO()
    print("{:-^30}".format("/token response"), file=stream)
    print(json_dumps(resp_data), file=stream)
    print("-" * 30, file=stream)
    log.debug(stream.getvalue())

    return resp_data
