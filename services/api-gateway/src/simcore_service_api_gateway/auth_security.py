""" Utility functions related with security

"""
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import jwt
from jwt import PyJWTError
from passlib.context import CryptContext
from pydantic import ValidationError

from . import crud_users as crud
from .schemas import TokenData, UserInDB

log = logging.getLogger(__name__)

# PASSWORDS ---------------------------------------------------------------

__pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return __pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return __pwd_context.hash(password)


def authenticate_user(username: str, password: str) -> Optional[UserInDB]:
    user = crud.get_user(username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


# JSON WEB TOKENS (JWT) --------------------------------------------------------------

__SIGNING_KEY__ = os.environ.get("SECRET_KEY")
__ALGORITHM__ = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


def create_access_token(
    *, subject: str, scopes: List[str] = None, expires_delta: timedelta = None
) -> str:
    if expires_delta is None:
        expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    # JWT specs define "Claim Names" for the encoded payload
    # SEE https://tools.ietf.org/html/rfc7519#section-4
    to_encode = {
        "sub": subject,
        "exp": datetime.utcnow() + expires_delta,
        "scopes": scopes or [],
    }
    encoded_jwt = jwt.encode(to_encode, __SIGNING_KEY__, algorithm=__ALGORITHM__)
    return encoded_jwt


def get_access_token_data(encoded_jwt: str) -> Optional[TokenData]:
    """
        Decodes and validates JWT and returns TokenData
        Returns None, if invalid token
    """
    try:
        # decode JWT [header.payload.signature] and get payload:
        payload: Dict = jwt.decode(
            encoded_jwt, __SIGNING_KEY__, algorithms=[__ALGORITHM__]
        )

        # FIXME: here we determine that the subject happens to be the username!
        username: str = payload.get("sub")
        if username is None:
            return None

        token_scopes = payload.get("scopes", [])

        # validate
        token_data = TokenData(scopes=token_scopes, username=username)

    except (PyJWTError, ValidationError):
        # invalid token!
        log.debug("Invalid token", exc_info=True)
        return None
    return token_data
