""" Core functionality and tools for user's registration

    - registration code
    - invitation code
"""
import json
import logging
from pprint import pformat
from typing import Dict

from aiohttp import web
from yarl import URL

from ..db_models import UserStatus
from .cfg import cfg
from .confirmation import (ConfirmationAction, get_expiration_date,
                           is_confirmation_expired, validate_confirmation_code)
from .storage import AsyncpgStorage

log = logging.getLogger(__name__)


async def check_registration(email: str, password: str, confirm: str, db: AsyncpgStorage):
    # email : required & formats
    # password: required & secure[min length, ...]

    # If the email field is missing, return a 400 - HTTPBadRequest
    if email is None or password is None:
        raise web.HTTPBadRequest(reason="Email and password required",
                                    content_type='application/json')

    if confirm and password != confirm:
        raise web.HTTPConflict(reason=cfg.MSG_PASSWORD_MISMATCH,
                               content_type='application/json')

    # TODO: If the email field isn’t a valid email, return a 422 - HTTPUnprocessableEntity
    # TODO: If the password field is too short, return a 422 - HTTPUnprocessableEntity
    # TODO: use passwordmeter to enforce good passwords, but first create helper in front-end

    user = await db.get_user({'email': email})
    if user:
        # Resets pending confirmation if re-registers?
        if user['status'] == UserStatus.CONFIRMATION_PENDING.value:
            _confirmation = await db.get_confirmation({
                'user': user,
                'action': ConfirmationAction.REGISTRATION.value
            })

            if is_confirmation_expired(_confirmation):
                await db.delete_confirmation(_confirmation)
                await db.delete_user(user)
                return

        # If the email is already taken, return a 409 - HTTPConflict
        raise web.HTTPConflict(reason=cfg.MSG_EMAIL_EXISTS,
                               content_type='application/json')

    log.debug("Registration data validated")

async def create_invitation(host:Dict, guest:str, db:AsyncpgStorage):
    """ Creates an invitation token for a guest to register in the platform

        Creates and injects an invitation token in the confirmation table associated
        to the host user

    :param host: valid user that creates the invitation
    :type host: Dict-like
    :param guest: some description of the guest, e.g. email, name or a json
    """
    confirmation = await db.create_confirmation(
        user=host,
        action=ConfirmationAction.INVITATION.name,
        data= json.dumps({
            "created_by": host['email'],
            "guest": guest
        })
    )
    return confirmation

async def check_invitation(invitation:str, db:AsyncpgStorage):
    confirmation = None
    if invitation:
        confirmation = await validate_confirmation_code(invitation, db)

    if confirmation:
        #FIXME: check if action=invitation??
        log.info("Invitation code used. Deleting %s", pformat(get_confirmation_info(confirmation)))
        await db.delete_confirmation(confirmation)
    else:
        raise web.HTTPForbidden(reason=("Invalid invitation code."
                                        "Your invitation was already used or might have expired."
                                        "Please contact our support team to get a new one.") )

def get_confirmation_info(confirmation):
    info = dict(confirmation)
    # data column is a string
    try:
        info['data'] = json.loads(confirmation['data'])
    except json.decoder.JSONDecodeError:
        log.warning("Failed to load data from confirmation. Skipping 'data' field.")

    # extra
    info["expires"] = get_expiration_date(confirmation)

    if confirmation['action']==ConfirmationAction.INVITATION.name:
        info["url"] = get_invitation_url(confirmation)

    return info

def get_invitation_url(confirmation, origin: URL=None) -> URL:
    code = confirmation['code']
    is_invitation = confirmation['action'] == ConfirmationAction.INVITATION.name

    if origin is None or not is_invitation:
        origin = URL()

    # https://some-web-url.io/#/registration/?invitation={code}
    return origin.with_fragment("/registration/?invitation={}".format(code))
