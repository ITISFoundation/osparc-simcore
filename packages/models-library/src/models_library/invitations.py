from datetime import datetime, timezone
from typing import Final

from pydantic import BaseModel, EmailStr, Field, PositiveInt, field_validator

from .products import ProductName

_MAX_LEN: Final = 40


class InvitationInputs(BaseModel):
    """Input data necessary to create an invitation"""

    issuer: str = Field(
        ...,
        description="Identifies who issued the invitation. E.g. an email, a service name etc. NOTE: it will be trimmed if exceeds maximum",
        min_length=1,
        max_length=_MAX_LEN,
    )
    guest: EmailStr = Field(
        ...,
        description="Invitee's email. Note that the registration can ONLY be used with this email",
    )
    trial_account_days: PositiveInt | None = Field(
        default=None,
        description="If set, this invitation will activate a trial account."
        "Sets the number of days from creation until the account expires",
    )
    extra_credits_in_usd: PositiveInt | None = Field(
        default=None,
        description="If set, the account's primary wallet will add extra credits corresponding to this ammount in USD",
    )
    product: ProductName | None = Field(
        default=None,
        description="If None, it will use INVITATIONS_DEFAULT_PRODUCT",
    )

    @field_validator("issuer", mode="before")
    @classmethod
    def trim_long_issuers_to_max_length(cls, v):
        if v and isinstance(v, str):
            return v[:_MAX_LEN]
        return v


class InvitationContent(InvitationInputs):
    """Data in an invitation"""

    # avoid using default to mark exactly the time
    created: datetime = Field(..., description="Timestamp for creation")

    def as_invitation_inputs(self) -> InvitationInputs:
        return self.model_validate(self.model_dump(exclude={"created"}))    # copy excluding "created"

    @classmethod
    def create_from_inputs(
        cls, invitation_inputs: InvitationInputs, default_product: ProductName
    ) -> "InvitationContent":

        kwargs = invitation_inputs.model_dump(exclude_none=True)
        kwargs.setdefault("product", default_product)
        return cls(
            created=datetime.now(tz=timezone.utc),
            **kwargs,
        )
