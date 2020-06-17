""" Utility functions related with security

"""
import os
from datetime import datetime, timedelta
from typing import Dict, Optional

import jwt
from jwt import PyJWTError
from loguru import logger
from pydantic import ValidationError

from ..models.schemas.tokens import TokenData

# JSON WEB TOKENS (JWT) --------------------------------------------------------------

__SIGNING_KEY__ = os.environ.get("SECRET_KEY")
__ALGORITHM__ = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


def create_access_token(
    data: TokenData, *, expires_in_mins: Optional[int] = ACCESS_TOKEN_EXPIRE_MINUTES
) -> str:
    """
        To disable expiration, set 'expires_in_mins' to None
    """
    # JWT specs define "Claim Names" for the encoded payload
    # SEE https://tools.ietf.org/html/rfc7519#section-4
    payload = {
        "sub": data.user_id,
        "scopes": data.scopes or [],
    }

    if expires_in_mins is not None:
        exp = datetime.utcnow() + timedelta(minutes=expires_in_mins)
        payload["exp"] = exp

    encoded_jwt = jwt.encode(payload, __SIGNING_KEY__, algorithm=__ALGORITHM__)
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

        token_data = TokenData(
            user_id=payload.get("sub"), token_scopes=payload.get("scopes", [])
        )

    except PyJWTError:
        logger.debug("Invalid token", exc_info=True)
        return None

    except ValidationError:
        logger.warning("Token data corrupted? Check payload -> TokenData conversion")
        return None

    return token_data
