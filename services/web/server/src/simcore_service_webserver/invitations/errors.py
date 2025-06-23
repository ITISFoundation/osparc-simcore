"""
API plugin errors
"""

from common_library.user_messages import user_message

from ..errors import WebServerBaseError

MSG_INVALID_INVITATION_URL = user_message("Link seems corrupted or incomplete")
MSG_INVITATION_ALREADY_USED = user_message("This invitation was already used")


class InvitationsError(WebServerBaseError, ValueError): ...


class InvalidInvitationError(InvitationsError):
    msg_template = "Invalid invitation"


class InvitationsServiceUnavailableError(InvitationsError):
    msg_template = "Cannot process invitations"
