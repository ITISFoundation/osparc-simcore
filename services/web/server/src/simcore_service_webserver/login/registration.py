""" Core functionality and tools for user's registration


"""
# TODO: Move handlers.check_registration  and other utils related with registration here
import json
import logging

from yarl import URL

from ..db_models import ConfirmationAction
from .storage import AsyncpgStorage
from .utils import get_expiration_date

log = logging.getLogger(__name__)

async def create_invitation(host, guest, db:AsyncpgStorage):
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


def get_confirmation_info(confirmation):
    info = confirmation

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
    assert confirmation['action'] == ConfirmationAction.INVITATION.name

    if origin is None:
        origin = URL()

    # https://some-web-url.io/#/registration/?invitation={code}
    return origin.with_fragment("/registration/?invitation={}".format(code))
