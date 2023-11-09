from datetime import datetime, timezone

from models_library.products import ProductName
from pydantic import BaseModel, EmailStr, Field, PositiveInt, validator


class InvitationInputs(BaseModel):
    """Input data necessary to create an invitation"""

    issuer: str = Field(
        ...,
        description="Identifies who issued the invitation. E.g. an email, a service name etc. NOTE: it will be trimmed if exceeds maximum",
        min_length=1,
        max_length=30,
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

    @validator("issuer", pre=True)
    @classmethod
    def trim_long_issuers_to_max_length(cls, v):
        if v and isinstance(v, str):
            return v[:29]
        return v


class InvitationContent(InvitationInputs):
    """Data in an invitation"""

    # avoid using default to mark exactly the time
    created: datetime = Field(..., description="Timestamp for creation")

    def as_invitation_inputs(self) -> InvitationInputs:
        return self.copy(exclude={"created"})

    @classmethod
    def create_from_inputs(
        cls, invitation_inputs: InvitationInputs, default_product: ProductName
    ) -> "InvitationContent":

        kwargs = invitation_inputs.dict(exclude_none=True)
        kwargs.setdefault("product", default_product)
        return cls(
            created=datetime.now(tz=timezone.utc),
            **kwargs,
        )
