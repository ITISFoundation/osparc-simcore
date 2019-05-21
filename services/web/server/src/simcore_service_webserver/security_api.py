""" API for security subsystem.

"""
# pylint: disable=assignment-from-no-return
import logging

import passlib.hash
import sqlalchemy as sa
from aiohttp_security.api import (authorized_userid, check_permission, forget,
                                  is_anonymous, remember)
from aiopg.sa import Engine

from .db_models import UserStatus, users

log = logging.getLogger(__file__)


async def check_credentials(engine: Engine, email: str, password: str) -> bool:
    async with engine.acquire() as conn:
        query = users.select().where(
            sa.and_(users.c.email == email,
            users.c.status != UserStatus.BANNED)
        )
        ret = await conn.execute(query)
        user = await ret.fetchone()
        if user is not None:
            return check_password(password, user['password_hash'] )
    return False

def encrypt_password(password):
    return passlib.hash.sha256_crypt.encrypt(password, rounds=1000)

def check_password(password, password_hash):
    return passlib.hash.sha256_crypt.verify(password, password_hash)


__all__ = (
    'encrypt_password', 'check_credentials',
    'authorized_userid', 'forget', 'remember', 'is_anonymous', 'check_permission'
)
