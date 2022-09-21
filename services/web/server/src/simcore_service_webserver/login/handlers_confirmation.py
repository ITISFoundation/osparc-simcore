import logging
from typing import Optional

from aiohttp import web
from pydantic import EmailStr, parse_obj_as
from servicelib.aiohttp.rest_utils import extract_and_validate
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from yarl import URL

from ..security_api import encrypt_password
from ._confirmation import validate_confirmation_code
from .settings import LoginOptions, get_plugin_options
from .storage import AsyncpgStorage, ConfirmationDict, get_plugin_storage
from .utils import ACTIVE, CHANGE_EMAIL, REGISTRATION, RESET_PASSWORD, flash_response

log = logging.getLogger(__name__)


async def email_confirmation(request: web.Request):
    """Handles email confirmation by checking a code passed as query parameter

    Retrieves confirmation key and redirects back to some location front-end

    * registration, change-email:
        - sets user as active
        - redirects to login
    * reset-password:
        - redirects to login
        - attaches page and token info onto the url
        - info appended as fragment, e.g. https://osparc.io#reset-password?code=131234
        - front-end should interpret that info as:
            - show the reset-password page
            - use the token to submit a POST /v0/auth/confirmation/{code} and finalize reset action
    """
    params, _, _ = await extract_and_validate(request)

    db: AsyncpgStorage = get_plugin_storage(request.app)
    cfg: LoginOptions = get_plugin_options(request.app)

    code = params["code"]

    confirmation: Optional[ConfirmationDict] = await validate_confirmation_code(
        code, db, cfg
    )
    redirect_url = URL(cfg.LOGIN_REDIRECT)

    if confirmation and (action := confirmation["action"]):
        if action == REGISTRATION:
            user = await db.get_user({"id": confirmation["user_id"]})
            await db.update_user(user, {"status": ACTIVE})
            await db.delete_confirmation(confirmation)
            redirect_url = redirect_url.with_fragment("?registered=true")
            log.debug(
                "%s registered -> %s",
                f"{user=}",
                f"{redirect_url=}",
            )

        elif action == CHANGE_EMAIL:
            #
            # TODO: compose error and send to front-end using fragments in the redirection
            # But first we need to implement this refactoring https://github.com/ITISFoundation/osparc-simcore/issues/1975
            #
            user_update = {"email": parse_obj_as(EmailStr, confirmation["data"])}
            user = await db.get_user({"id": confirmation["user_id"]})
            await db.update_user(user, user_update)
            await db.delete_confirmation(confirmation)
            log.debug(
                "%s updated %s",
                f"{user=}",
                f"{user_update}",
            )

        elif action == RESET_PASSWORD:
            # NOTE: By using fragments (instead of queries or path parameters), the browser does NOT reloads page
            redirect_url = redirect_url.with_fragment("reset-password?code=%s" % code)
            log.debug(
                "Reset password requested %s. %s",
                f"{confirmation=}",
                f"{redirect_url=}",
            )

    raise web.HTTPFound(location=redirect_url)


async def reset_password_allowed(request: web.Request):
    """Changes password using a token code without being logged in"""
    params, _, body = await extract_and_validate(request)

    db: AsyncpgStorage = get_plugin_storage(request.app)
    cfg: LoginOptions = get_plugin_options(request.app)

    code = params["code"]
    password = body.password
    confirm = body.confirm

    if password != confirm:
        raise web.HTTPConflict(
            reason=cfg.MSG_PASSWORD_MISMATCH, content_type=MIMETYPE_APPLICATION_JSON
        )  # 409

    confirmation = await validate_confirmation_code(code, db, cfg)

    if confirmation:
        user = await db.get_user({"id": confirmation["user_id"]})
        assert user  # nosec

        await db.update_user(user, {"password_hash": encrypt_password(password)})
        await db.delete_confirmation(confirmation)

        response = flash_response(cfg.MSG_PASSWORD_CHANGED)
        return response

    raise web.HTTPUnauthorized(
        reason="Cannot reset password. Invalid token or user",
        content_type=MIMETYPE_APPLICATION_JSON,
    )  # 401
