from datetime import UTC, datetime
from typing import Annotated, Final

from pydantic import (
    AfterValidator,
    BaseModel,
    EmailStr,
    Field,
    PositiveInt,
    field_validator,
)

from .products import ProductName

_MAX_LEN: Final = 40


class InvitationInputs(BaseModel):
    """Input data necessary to create an invitation"""

    issuer: Annotated[
        str,
        Field(
            description="Identifies who issued the invitation. E.g. an email, a service name etc. NOTE: it will be trimmed if exceeds maximum",
            min_length=1,
            max_length=_MAX_LEN,
        ),
    ]
    guest: Annotated[
        EmailStr,
        AfterValidator(lambda v: v.lower()),
        Field(
            description="Invitee's email. Note that the registration can ONLY be used with this email",
        ),
    ]
    trial_account_days: Annotated[
        PositiveInt | None,
        Field(
            description="If set, this invitation will activate a trial account."
            "Sets the number of days from creation until the account expires",
        ),
    ] = None
    extra_credits_in_usd: Annotated[
        PositiveInt | None,
        Field(
            description="If set, the account's primary wallet will add extra credits corresponding to this ammount in USD",
        ),
    ] = None
    product: Annotated[
        ProductName | None,
        Field(
            description="If None, it will use INVITATIONS_DEFAULT_PRODUCT",
        ),
    ] = None

    @field_validator("issuer", mode="before")
    @classmethod
    def trim_long_issuers_to_max_length(cls, v):
        if v and isinstance(v, str):
            return v[:_MAX_LEN]
        return v


class InvitationContent(InvitationInputs):
    """Data within an invitation"""

    # avoid using default to mark exactly the time
    created: Annotated[datetime, Field(description="Timestamp for creation")]

    def as_invitation_inputs(self) -> InvitationInputs:
        return self.model_validate(
            self.model_dump(exclude={"created"})
        )  # copy excluding "created"

    @classmethod
    def create_from_inputs(
        cls, invitation_inputs: InvitationInputs, default_product: ProductName
    ) -> "InvitationContent":
        kwargs = invitation_inputs.model_dump(exclude_none=True)
        kwargs.setdefault("product", default_product)
        return cls(
            created=datetime.now(tz=UTC),
            **kwargs,
        )
