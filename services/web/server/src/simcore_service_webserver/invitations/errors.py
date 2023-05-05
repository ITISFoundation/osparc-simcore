"""
    API plugin errors
"""


from pydantic.errors import PydanticErrorMixin


class InvitationsErrors(PydanticErrorMixin, ValueError):
    ...


class InvalidInvitation(InvitationsErrors):
    msg_template = "Invalid invitation. {reason}"


class InvitationsServiceUnavailable(InvitationsErrors):
    msg_template = (
        "Unable to process your invitation since the invitations service is currently unavailable. "
        "Please try again later."
    )
