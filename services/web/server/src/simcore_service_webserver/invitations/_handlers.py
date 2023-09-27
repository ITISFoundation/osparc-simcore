import logging
from datetime import datetime, timezone

from aiohttp import web
from models_library.api_schemas_webserver.product import (
    GenerateInvitation,
    InvitationGet,
)
from models_library.users import UserID
from pydantic import Field
from servicelib.aiohttp.requests_validation import RequestParams, parse_request_body_as
from servicelib.request_keys import RQT_USERID_KEY
from simcore_service_webserver.utils_aiohttp import envelope_json_response

from .._constants import RQ_PRODUCT_KEY
from .._meta import API_VTAG as VTAG
from ..login.decorators import login_required
from ..security.decorators import permission_required
from ..users.api import get_user_name_and_email

routes = web.RouteTableDef()


_logger = logging.getLogger(__name__)


class _ProductsRequestContext(RequestParams):
    user_id: UserID = Field(..., alias=RQT_USERID_KEY)
    product_name: str = Field(..., alias=RQ_PRODUCT_KEY)


@routes.get(f"/{VTAG}/invitation:generate", name="generate_invitation")
@login_required
@permission_required("product.invitations")
async def generate_invitation(request: web.Request):
    req_ctx = _ProductsRequestContext.parse_obj(request)
    body = await parse_request_body_as(GenerateInvitation, request)

    _, user_email = await get_user_name_and_email(request.app, user_id=req_ctx.user_id)

    invitation = InvitationGet.parse_obj(
        {
            **body.dict(),
            "product_name": req_ctx.product_name,
            "issuer": user_email,
            "created": datetime.now(tz=timezone.utc),
            "invitation_url": request.url.origin().with_path("/fake-invitation"),
        }
    )
    return envelope_json_response(invitation)
