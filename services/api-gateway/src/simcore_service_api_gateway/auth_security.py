""" Utility functions related with security

"""
import os
import subprocess
from datetime import datetime, timedelta
from subprocess import CalledProcessError, CompletedProcess

import jwt
from passlib.context import CryptContext
from typing import List

# PASSWORDS
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_secret_key() -> str:
    # NOTICE that this key is reset when server is restarted!
    try:
        proc: CompletedProcess = subprocess.run("openssl rand -hex 32", check=True)
    except CalledProcessError as why:
        raise ValueError(f"Cannot create secret key") from why
    return str(proc.stdout).strip()


__SIGNING_KEY__ = os.environ.get("SECRET_KEY") or create_secret_key()
__ALGORITHM__  = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


def create_access_jwt_token(*,
    subject: str,
    scopes: List[str],
    expires_delta: timedelta = None) -> str:
    if expires_delta is None:
        expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    # The JWT specification says that there's a key sub, with the subject of the token.
    to_encode = {
        "sub": subject,
        "exp": datetime.utcnow() + expires_delta,
        "scopes": scopes
    }
    encoded_jwt = jwt.encode(to_encode, __SIGNING_KEY__, algorithm=__ALGORITHM__)
    return encoded_jwt


def decode_token(encoded_jwt: str) -> dict:
    return jwt.decode(encoded_jwt, __SIGNING_KEY__, algorithms=[__ALGORITHM__])


from jwt import PyJWTError
from typing import Optional
from .schemas import TokenData, ValidationError


def get_access_token_data(token: str) -> Optional[TokenData]:
    """
        Decodes and validates
    """
    # returns valid
    try:
        # decode JWT [header.payload.signature] and get payload:
        payload = decode_token(token)

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
