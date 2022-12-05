import logging
from typing import Optional

from aiohttp import web
from aiohttp.web import RouteTableDef
from pydantic import EmailStr, parse_obj_as
from servicelib.aiohttp.rest_utils import extract_and_validate
from servicelib.logging_utils import log_context
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from simcore_postgres_database.errors import UniqueViolation
from yarl import URL

from ..security_api import encrypt_password, remember
from ..utils import MINUTE
from ..utils_rate_limiting import global_rate_limit_route
from ._2fa import delete_2fa_code, get_2fa_code
from ._confirmation import validate_confirmation_code
from .settings import (
    LoginOptions,
    LoginSettings,
    get_plugin_options,
    get_plugin_settings,
)
from .storage import AsyncpgStorage, ConfirmationTokenDict, get_plugin_storage
from .utils import ACTIVE, CHANGE_EMAIL, REGISTRATION, RESET_PASSWORD, flash_response

log = logging.getLogger(__name__)


routes = RouteTableDef()


@routes.get("/auth/confirmation/{code}", name="auth_confirmation")
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

    confirmation: Optional[ConfirmationTokenDict] = await validate_confirmation_code(
        code, db=db, cfg=cfg
    )

    redirect_to_login_url = URL(cfg.LOGIN_REDIRECT)
    if confirmation and (action := confirmation["action"]):
        if action == REGISTRATION:
            user = await db.get_user({"id": confirmation["user_id"]})
            # FIXME: update+delete have to be atomic!
            await db.update_user(user, {"status": ACTIVE})
            await db.delete_confirmation(confirmation)
            redirect_to_login_url = redirect_to_login_url.with_fragment(
                "?registered=true"
            )
            log.debug(
                "%s registered -> %s",
                f"{user=}",
                f"{redirect_to_login_url=}",
            )

        elif action == CHANGE_EMAIL:
            #
            # TODO: compose error and send to front-end using fragments in the redirection
            # But first we need to implement this refactoring https://github.com/ITISFoundation/osparc-simcore/issues/1975
            #

            # FIXME: ERROR HANDLING
            # notice that this is a redirection from an email, meaning that the
            # response has to be TXT!!!

            user_update = {"email": parse_obj_as(EmailStr, confirmation["data"])}
            user = await db.get_user({"id": confirmation["user_id"]})
            # FIXME: update+delete have to be atomic!
            await db.update_user(user, user_update)
            await db.delete_confirmation(confirmation)
            log.debug(
                "%s updated %s",
                f"{user=}",
                f"{user_update}",
            )

        elif action == RESET_PASSWORD:
            # NOTE: By using fragments (instead of queries or path parameters), the browser does NOT reloads page
            redirect_to_login_url = redirect_to_login_url.with_fragment(
                "reset-password?code=%s" % code
            )
            log.debug(
                "Reset password requested %s. %s",
                f"{confirmation=}",
                f"{redirect_to_login_url=}",
            )

    raise web.HTTPFound(location=redirect_to_login_url)


@global_rate_limit_route(number_of_requests=5, interval_seconds=MINUTE)
@routes.post("/auth/validate-code-register", name="auth_validate_2fa_register")
async def phone_confirmation(request: web.Request):
    _, _, body = await extract_and_validate(request)

    settings: LoginSettings = get_plugin_settings(request.app)
    db: AsyncpgStorage = get_plugin_storage(request.app)
    cfg: LoginOptions = get_plugin_options(request.app)

    email = body.email
    phone = body.phone
    code = body.code

    if not settings.LOGIN_2FA_REQUIRED:
        raise web.HTTPServiceUnavailable(
            reason="Phone registration is not available",
            content_type=MIMETYPE_APPLICATION_JSON,
        )

    if (expected := await get_2fa_code(request.app, email)) and code == expected:
        await delete_2fa_code(request.app, email)

        # db
        try:
            user = await db.get_user({"email": email})
            await db.update_user(user, {"phone": phone})

        except UniqueViolation as err:
            raise web.HTTPUnauthorized(
                reason="Invalid phone number",
                content_type=MIMETYPE_APPLICATION_JSON,
            ) from err

        # login
        with log_context(
            log,
            logging.INFO,
            "login after phone_confirmation of user_id=%s with %s",
            f"{user.get('id')}",
            f"{email=}",
        ):
            identity = user["email"]
            response = flash_response(cfg.MSG_LOGGED_IN, "INFO")
            await remember(request, response, identity)
            return response

    # unauthorized
    raise web.HTTPUnauthorized(
        reason="Invalid 2FA code", content_type=MIMETYPE_APPLICATION_JSON
    )


@routes.post("/auth/reset-password/{code}", name="auth_reset_password_allowed")
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
