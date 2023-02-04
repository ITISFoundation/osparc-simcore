from typing import Any, Literal, Optional

from aiohttp import web
from pydantic import BaseModel, EmailStr, Field
from servicelib.aiohttp.requests_validation import parse_request_body_as

from ._meta import API_VTAG
from .email_core import send_email_from_template
from .login.decorators import login_required
from .products import Product, get_current_product, get_product_template_path
from .security_decorators import permission_required
from .utils_aiohttp import envelope_json_response

routes = web.RouteTableDef()


class TestEmail(BaseModel):
    from_: Optional[EmailStr] = Field(None, description="Email sender")
    to: EmailStr = Field(..., description="Email destination")
    template_name: Literal[
        "change_email_email.jinja2",
        "new_2fa_code.jinja2",
        "registration_email.jinja2",
        "reset_password_email_failed.jinja2",
        "reset_password_email.jinja2",
        "service_submission.jinja2",
    ] = "registration_email.jinja2"
    template_context: dict[str, Any] = {}


@routes.post(f"/{API_VTAG}/email:test")
@login_required
@permission_required("admin.*")
async def test_email(request: web.Request):
    """Tests email by rendering and sending a template email to some address destination"""

    body = await parse_request_body_as(TestEmail, request)

    template_path = get_product_template_path(request, filename=body.template_name)
    product: Product = get_current_product(request)

    context = {
        "host": request.host,
        "link": "https://httpbin.org/redirect-to?url=https%3A%2F%2Fhttpbin.org%2F",
        "name": "Mr. Smith",
        "support_email": product.support_email,
    } | body.template_context

    await send_email_from_template(
        request,
        from_=body.from_ or product.support_email,
        to=body.to,
        template=template_path,
        context=context,
    )

    return envelope_json_response(body)
