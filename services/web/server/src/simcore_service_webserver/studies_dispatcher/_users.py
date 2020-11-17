""" Users management

 Keeps functionality that couples with the following app modules
    - users,
    - login
    - security
    - resource_manager

"""
import logging
from typing import Dict

from aiohttp import web
from aioredlock import Aioredlock
from pydantic import BaseModel

from ..login.cfg import get_storage
from ..login.handlers import ACTIVE, GUEST
from ..login.utils import get_client_ip, get_random_string
from ..resource_manager.config import (
    APP_CLIENT_REDIS_LOCK_KEY,
    GUEST_USER_RC_LOCK_FORMAT,
)
from ..security_api import authorized_userid, encrypt_password, is_anonymous, remember
from ..users_api import get_user

log = logging.getLogger(__name__)


class UserInfo(BaseModel):
    id: int
    name: str
    email: str
    primary_gid: int
    needs_login: bool = False
    is_guest: bool = True


async def acquire_user(request: web.Request) -> UserInfo:
    """
    Identifies request's user and if anonymous, it creates
    a temporary guest user that is autho
    """

    # Get or create a valid user
    user = None
    is_anonymous_user = await is_anonymous(request)
    if not is_anonymous_user:
        # NOTE: covers valid cookie with unauthorized user (e.g. expired guest/banned)
        # TODO: test if temp user overrides old cookie properly
        user = await _get_authorized_user(request)

    if not user:
        log.debug("Creating temporary user ...")
        user = await _create_temporary_user(request)
        is_anonymous_user = True

    return UserInfo(
        id=user["id"],
        name=user["name"],
        email=user["email"],
        primary_gid=user["primary_gid"],
        needs_login=is_anonymous_user,
        is_guest=user.get("role") == GUEST,
    )


async def ensure_authentication(
    user: UserInfo, request: web.Request, response: web.Response
):
    if user.needs_login:
        log.debug("Auto login for anonymous user %s", user["name"])
        identity = user.email
        await remember(request, response, identity)


async def _get_authorized_user(request: web.Request) -> Dict:
    db = get_storage(request.app)
    userid = await authorized_userid(request)
    user = await get_user(request.app, userid)
    return user


async def _create_temporary_user(request: web.Request):
    db = get_storage(request.app)
    lock_manager: Aioredlock = request.app[APP_CLIENT_REDIS_LOCK_KEY]

    # TODO: avatar is an icon of the hero!
    random_uname = get_random_string(min_len=5)
    email = random_uname + "@guest-at-osparc.io"
    password = get_random_string(min_len=12)

    # GUEST_USER_RC_LOCK:
    #
    #   These locks prevents the GC from deleting a GUEST user in to stages of its lifefime:
    #
    #  1. During construction:
    #     - Prevents GC from deleting this GUEST user while it is being created
    #     - Since the user still does not have an ID assigned, the lock is named with his random_uname
    #
    MAX_DELAY_TO_CREATE_USER = 3  # secs
    #
    #  2. During initialization
    #     - Prevents the GC from deleting this GUEST user, with ID assigned, while it gets initialized and acquires it's first resource
    #     - Uses the ID assigned to name the lock
    #
    MAX_DELAY_TO_GUEST_FIRST_CONNECTION = 15  # secs
    #
    #
    # NOTES:
    #   - In case of failure or excessive delay the lock has a timeout that automatically unlocks it
    #     and the GC can clean up what remains
    #   - Notice that the ids to name the locks are unique, therefore the lock can be acquired w/o errors
    #   - These locks are very specific to resources and have timeout so the risk of blocking from GC is small
    #

    # (1) read details above
    async with await lock_manager.lock(
        GUEST_USER_RC_LOCK_FORMAT.format(user_id=random_uname),
        lock_timeout=MAX_DELAY_TO_CREATE_USER,
    ):
        # NOTE: usr Dict is incomplete, e.g. does not contain primary_gid
        usr = await db.create_user(
            {
                "name": random_uname,
                "email": email,
                "password_hash": encrypt_password(password),
                "status": ACTIVE,
                "role": GUEST,
                "created_ip": get_client_ip(request),
            }
        )
        user: Dict = await get_user(request.app, usr["id"])

        # (2) read details above
        await lock_manager.lock(
            GUEST_USER_RC_LOCK_FORMAT.format(user_id=user["id"]),
            lock_timeout=MAX_DELAY_TO_GUEST_FIRST_CONNECTION,
        )

    return user
