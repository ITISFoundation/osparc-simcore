"""Context model for the 'account_approved' email template."""

from models_library.notifications import Channel
from pydantic import BaseModel, HttpUrl

from ..template import BaseTemplateContext, register_template_context


class User(BaseModel):
    first_name: str | None = None


@register_template_context(channel=Channel.email, template_name="account_approved")
class AccountApprovedTemplateContext(BaseTemplateContext):
    user: User
    link: HttpUrl

    # extra fields provided by frontend
    trial_account_days: int | None = None
    # NOTE: We expose extra credits (not USD)
    # https://github.com/ITISFoundation/osparc-simcore/pull/8899#:~:text=https%3A//z43.fogbugz.com/f/cases/235281/Send%2Demails%2Dto%2Dusers%2Dfrom%2Dthe%2DPO%2DCenter%23BugEvent.1765946
    extra_credits: int | None = None
