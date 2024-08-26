import logging

from aiohttp import web
from models_library.api_schemas_invitations.invitations import ApiInvitationInputs
from models_library.api_schemas_webserver.product import (
    GenerateInvitation,
    InvitationGenerated,
)
from models_library.users import UserID
from pydantic import Field
from servicelib.aiohttp.requests_validation import RequestParams, parse_request_body_as
from servicelib.request_keys import RQT_USERID_KEY
from simcore_service_webserver.utils_aiohttp import envelope_json_response
from yarl import URL

from .._constants import RQ_PRODUCT_KEY
from .._meta import API_VTAG as VTAG
from ..invitations import api
from ..login.decorators import login_required
from ..security.decorators import permission_required
from ..users.api import get_user_name_and_email

routes = web.RouteTableDef()


_logger = logging.getLogger(__name__)


class _ProductsRequestContext(RequestParams):
    user_id: UserID = Field(..., alias=RQT_USERID_KEY)  # type: ignore[literal-required]
    product_name: str = Field(..., alias=RQ_PRODUCT_KEY)  # type: ignore[literal-required]


@routes.post(f"/{VTAG}/invitation:generate", name="generate_invitation")
@login_required
@permission_required("product.invitations.create")
async def generate_invitation(request: web.Request):
    req_ctx = _ProductsRequestContext.parse_obj(request)
    body = await parse_request_body_as(GenerateInvitation, request)

    _, user_email = await get_user_name_and_email(request.app, user_id=req_ctx.user_id)

    # NOTE: check if invitations are activated in this product or raise
    generated = await api.generate_invitation(
        request.app,
        ApiInvitationInputs(
            issuer=user_email,
            trial_account_days=body.trial_account_days,
            guest=body.guest,
            extra_credits_in_usd=body.extra_credits_in_usd,
            product=req_ctx.product_name,
        ),
    )
    assert request.url.host  # nosec
    assert generated.product == req_ctx.product_name  # nosec
    assert generated.guest == body.guest  # nosec

    url = URL(generated.invitation_url)
    invitation_link = request.url.with_path(url.path).with_fragment(url.raw_fragment)

    invitation = InvitationGenerated(
        product_name=generated.product,
        issuer=generated.issuer,  # type: ignore[arg-type]
        guest=generated.guest,  # type: ignore[arg-type]
        trial_account_days=generated.trial_account_days,
        extra_credits_in_usd=generated.extra_credits_in_usd,
        created=generated.created,
        invitation_link=f"{invitation_link}",  # type: ignore[arg-type]
    )
    return envelope_json_response(invitation.dict(exclude_none=True))
