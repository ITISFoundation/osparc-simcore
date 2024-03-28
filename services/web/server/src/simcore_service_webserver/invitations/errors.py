"""
    API plugin errors
"""


from ..errors import WebServerBaseError

MSG_INVALID_INVITATION_URL = "Link seems corrupted or incomplete"
MSG_INVITATION_ALREADY_USED = "This invitation was already used"


class InvitationsError(WebServerBaseError, ValueError):
    ...


class InvalidInvitationError(InvitationsError):
    msg_template = "Invalid invitation. {reason}"


class InvitationsServiceUnavailableError(InvitationsError):
    msg_template = (
        "Unable to process your invitation since the invitations service is currently unavailable. "
        "Please try again later."
    )
