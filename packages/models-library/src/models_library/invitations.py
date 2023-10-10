from datetime import datetime

from pydantic import BaseModel, Field, PositiveInt

from .emails import LowerCaseEmailStr


class InvitationInputs(BaseModel):
    """Input data necessary to create an invitation"""

    issuer: str = Field(
        ...,
        description="Identifies who issued the invitation. E.g. an email, a service name etc",
        min_length=1,
        max_length=30,
    )
    guest: LowerCaseEmailStr = Field(
        ...,
        description="Invitee's email. Note that the registration can ONLY be used with this email",
    )
    trial_account_days: PositiveInt | None = Field(
        None,
        description="If set, this invitation will activate a trial account."
        "Sets the number of days from creation until the account expires",
    )
    extra_credits: PositiveInt | None = Field(
        None,
        description="If set, the account's primary wallet will add these extra credits",
    )


class InvitationContent(InvitationInputs):
    """Data in an invitation"""

    # avoid using default to mark exactly the time
    created: datetime = Field(..., description="Timestamp for creation")

    def as_invitation_inputs(self) -> InvitationInputs:
        return self.copy(exclude={"created"})
