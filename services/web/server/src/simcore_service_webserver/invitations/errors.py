"""
API plugin errors
"""

from common_library.user_messages import user_message

from ..errors import WebServerBaseError

MSG_INVALID_INVITATION_URL = user_message(
    "The invitation link appears to be corrupted or incomplete.", _version=1
)
MSG_INVITATION_ALREADY_USED = user_message(
    "This invitation has already been used and cannot be used again.", _version=1
)


class InvitationsError(WebServerBaseError, ValueError): ...


class InvalidInvitationError(InvitationsError):
    msg_template = "Invalid invitation"


class InvitationsServiceUnavailableError(InvitationsError):
    msg_template = "Cannot process invitations"
