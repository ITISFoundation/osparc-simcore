""" Users management

 Keeps functionality that couples with the following app modules
    - users,
    - login
    - security
    - resource_manager

"""
import logging
from datetime import datetime

import redis.asyncio as aioredis
from aiohttp import web
from models_library.emails import LowerCaseEmailStr
from pydantic import BaseModel, parse_obj_as
from servicelib.logging_utils import log_decorator

from ..garbage_collector_settings import GUEST_USER_RC_LOCK_FORMAT
from ..login.storage import AsyncpgStorage, get_plugin_storage
from ..login.utils import ACTIVE, GUEST, get_client_ip, get_random_string
from ..redis import get_redis_lock_manager_client
from ..security.api import authorized_userid, encrypt_password, is_anonymous, remember
from ..users.api import get_user
from ..users.exceptions import UserNotFoundError
from ._constants import MSG_GUESTS_NOT_ALLOWED
from .settings import StudiesDispatcherSettings, get_plugin_settings

_logger = logging.getLogger(__name__)


class UserInfo(BaseModel):
    id: int
    name: str
    email: str
    primary_gid: int
    needs_login: bool = False
    is_guest: bool = True


async def _get_authorized_user(request: web.Request) -> dict:
    # Returns valid user if it is identified (cookie) and logged in (valid cookie)?
    user_id = await authorized_userid(request)
    if user_id is not None:
        try:
            user = await get_user(request.app, user_id)
            return user
        except UserNotFoundError:
            return {}
    return {}


async def _create_temporary_guest_user(request: web.Request):
    db: AsyncpgStorage = get_plugin_storage(request.app)
    redis_locks_client: aioredis.Redis = get_redis_lock_manager_client(request.app)
    settings: StudiesDispatcherSettings = get_plugin_settings(app=request.app)

    random_user_name = get_random_string(min_len=5)
    email = parse_obj_as(LowerCaseEmailStr, f"{random_user_name}@guest-at-osparc.io")
    password = get_random_string(min_len=12)
    expires_at = datetime.utcnow() + settings.STUDIES_GUEST_ACCOUNT_LIFETIME

    # GUEST_USER_RC_LOCK:
    #
    #   These locks prevents the GC from deleting a GUEST user in to stages of its lifefime:
    #
    #  1. During construction:
    #     - Prevents GC from deleting this GUEST user while it is being created
    #     - Since the user still does not have an ID assigned, the lock is named with his random_user_name
    #     - the timeout here is the TTL of the lock in Redis. in case the webserver is overwhelmed and cannot create
    #       a user during that time or crashes, then redis will ensure the lock disappears and let the garbage collector do its work
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
    async with redis_locks_client.lock(
        GUEST_USER_RC_LOCK_FORMAT.format(user_id=random_user_name),
        timeout=MAX_DELAY_TO_CREATE_USER,
    ):
        # NOTE: usr Dict is incomplete, e.g. does not contain primary_gid
        usr = await db.create_user(
            {
                "name": random_user_name,
                "email": email,
                "password_hash": encrypt_password(password),
                "status": ACTIVE,
                "role": GUEST,
                "created_ip": get_client_ip(request),
                "expires_at": expires_at,
            }
        )
        user: dict = await get_user(request.app, usr["id"])

        # (2) read details above
        await redis_locks_client.lock(
            GUEST_USER_RC_LOCK_FORMAT.format(user_id=user["id"]),
            timeout=MAX_DELAY_TO_GUEST_FIRST_CONNECTION,
        ).acquire()

    return user


@log_decorator(_logger, level=logging.DEBUG)
async def get_or_create_guest_user(
    request: web.Request, *, allow_anonymous_or_guest_users: bool
) -> UserInfo:
    """
    A user w/o authentication is denoted ANONYMOUS. If allow_anonymous_or_guest_users=True, then
    these users can be automatically promoted to GUEST. For that, a temporary guest account
    is created and associated to this user.

    GUEST users are therefore a special user that is un-identified to us (no email/name, etc)

    NOTE that if allow_anonymous_or_guest_users=False, GUEST users are NOT allowed in the system either.

    Arguments:
        allow_anonymous_or_guest_users -- if True, it will create a temporary GUEST account

    Raises:
        web.HTTPUnauthorized if ANONYMOUS users are not allowed (either w/o auth or as GUEST)

    """
    user = None

    # anonymous = no identity in request
    is_anonymous_user = await is_anonymous(request)
    if not is_anonymous_user:
        # NOTE: covers valid cookie with unauthorized user (e.g. expired guest/banned)
        user = await _get_authorized_user(request)

    if not user and allow_anonymous_or_guest_users:
        _logger.debug("Anonymous user is accepted as guest...")
        user = await _create_temporary_guest_user(request)
        is_anonymous_user = True

    if not allow_anonymous_or_guest_users and (not user or user.get("role") == GUEST):
        # NOTE: if allow_anonymous_users=False then GUEST users are NOT allowed!
        raise web.HTTPUnauthorized(reason=MSG_GUESTS_NOT_ALLOWED)

    assert isinstance(user, dict)  # nosec

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
        _logger.debug("Auto login for anonymous user %s", user.name)
        identity = user.email
        await remember(request, response, identity)
