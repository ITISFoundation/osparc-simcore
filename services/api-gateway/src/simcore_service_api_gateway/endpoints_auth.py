import logging
import os
from io import StringIO
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from . import crud_users as crud
from .api_dependencies_db import SAConnection, get_db_connection
from .auth_security import authenticate_user, create_access_token
from .schemas import Token, TokenData, UserInDB
from .utils.helpers import json_dumps

log = logging.getLogger(__name__)


router = APIRouter()


def _compose_msg(*, fd=None, rd=None) -> str:
    assert not (fd ^ rd), "Mutally exclusive"  # nosec

    stream = StringIO()

    if fd:
        print("Form Request", "-" * 20, file=stream)
        for (
            attr
        ) in "grant_type username password scopes client_id client_secret".split():
            print("-", attr, ":", getattr(fd, attr), file=stream)
        print("-" * 20, file=stream)
    elif rd:
        print("{:-^30}".format("/token response"), file=stream)
        print(json_dumps(rd), file=stream)
        print("-" * 30, file=stream)

    return stream.getvalue()


# NOTE: this path has to be the same as simcore_service_api_gateway.auth.oauth2_scheme
@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    conn: SAConnection = Depends(get_db_connection),
):
    """
        Returns an access-token provided a valid authorization grant
    """

    #
    # - This entrypoint is part of the Authorization Server
    # - Implements access point to obtain access-tokens
    #
    # |        |                               +---------------+
    # |        |--(C)-- Authorization Grant -->| Authorization |
    # | Client |                               |     Server    | Token request
    # |        |<-(D)----- Access Token -------|               |
    # |        |                               +---------------+
    #

    log.debug(_compose_msg(fd=form_data))

    user_id: Optional[int] = await crud.get_user_id(
        conn, api_key=form_data.username, api_secret=form_data.password
    )

    # TODO: check is NOT banned

    if not user_id:
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    # FIXME: expiration disabled since for the moment we do NOT have any renewal mechanims in place!!!
    access_token = create_access_token(TokenData(user_id), expires_in_mins=None)

    # NOTE: this reponse is defined in Oath2
    resp_data = {"access_token": access_token, "token_type": "bearer"}

    log.debug(_compose_msg(rd=resp_data))

    return resp_data
