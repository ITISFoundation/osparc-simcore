""" Utility functions related with security

"""
import logging
import os
import subprocess
from datetime import datetime, timedelta
from subprocess import CalledProcessError, CompletedProcess
from typing import List, Optional, Dict

import jwt
from jwt import PyJWTError
from passlib.context import CryptContext

from . import crud_users as crud
from .schemas import TokenData, UserInDB, ValidationError

log = logging.getLogger(__name__)

# PASSWORDS
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def authenticate_user(username: str, password: str) -> Optional[UserInDB]:
    user = crud.get_user(username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def create_secret_key() -> str:
    # NOTICE that this key is reset when server is restarted!
    try:
        proc: CompletedProcess = subprocess.run("openssl rand -hex 32", check=True, shell=True)
    except (CalledProcessError, FileNotFoundError) as why:
        raise ValueError(f"Cannot create secret key") from why
    log.warning("Created new secret key!!")
    return str(proc.stdout).strip()


# JSON WEB TOKENS (JWT)

__SIGNING_KEY__ = os.environ.get("SECRET_KEY")
__ALGORITHM__ = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


def create_access_token(
    *, subject: str, scopes: List[str] = None, expires_delta: timedelta = None
) -> str:
    if expires_delta is None:
        expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    # The JWT specification says that there's a key sub, with the subject of the token.
    to_encode = {
        "sub": subject,
        "exp": datetime.utcnow() + expires_delta,
        "scopes": scopes or [],
    }
    encoded_jwt = jwt.encode(to_encode, __SIGNING_KEY__, algorithm=__ALGORITHM__)
    return encoded_jwt


def decode_token(encoded_jwt: str) -> Dict:
    return jwt.decode(encoded_jwt, __SIGNING_KEY__, algorithms=[__ALGORITHM__])


def get_access_token_data(encoded_jwt: str) -> Optional[TokenData]:
    """
        Decodes and validates
    """
    # returns valid
    try:
        # decode JWT [header.payload.signature] and get payload:
        payload:Dict = decode_token(encoded_jwt)

        username: str = payload.get("sub")
        if username is None:
            return None
        token_scopes = payload.get("scopes", [])

        # validate
        token_data = TokenData(scopes=token_scopes, username=username)

    except (PyJWTError, ValidationError):
        # invalid token!
        return None
    return token_data
