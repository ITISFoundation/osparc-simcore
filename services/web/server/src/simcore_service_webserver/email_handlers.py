import logging
from typing import Any, Literal, Optional

from aiohttp import web
from pydantic import BaseModel, EmailStr, Field
from servicelib.aiohttp.requests_validation import parse_request_body_as

from ._meta import API_VTAG
from .email_core import (
    check_email_server_responsiveness,
    get_plugin_settings,
    send_email_from_template,
)
from .login.decorators import login_required
from .products import Product, get_current_product, get_product_template_path
from .security_decorators import permission_required
from .utils import get_traceback_string
from .utils_aiohttp import envelope_json_response

logger = logging.getLogger(__name__)


#
# API schema models
#


class TestEmail(BaseModel):
    from_: Optional[EmailStr] = Field(None, description="Email sender")
    to: EmailStr = Field(..., description="Email receiver")
    template_name: Literal[
        "change_email_email.jinja2",
        "new_2fa_code.jinja2",
        "registration_email.jinja2",
        "reset_password_email_failed.jinja2",
        "reset_password_email.jinja2",
        "service_submission.jinja2",
    ] = "registration_email.jinja2"
    template_context: dict[str, Any] = {}


class TestFailed(BaseModel):
    test_name: str
    error_type: str
    error_message: str
    traceback: str

    @classmethod
    def create_from_exception(cls, error: Exception, test_name: str):
        return cls(
            test_name=test_name,
            error_type=f"{type(error)}",
            error_message=f"{error}",
            traceback=get_traceback_string(error),
        )


class TestPassed(BaseModel):
    fixtures: dict[str, Any]
    info: dict[str, Any]


#
# API routes
#
routes = web.RouteTableDef()


@routes.post(f"/{API_VTAG}/email:test")
@login_required
@permission_required("admin.*")
async def test_email(request: web.Request):
    """Tests email by rendering and sending a template email to some address destination"""

    body = await parse_request_body_as(TestEmail, request)

    product: Product = get_current_product(request)

    template_path = await get_product_template_path(
        request, filename=body.template_name
    )

    context = {
        "host": request.host,
        "link": "https://httpbin.org/redirect-to?url=https%3A%2F%2Fhttpbin.org%2F",
        "name": "Mr. Smith",
        "support_email": product.support_email,
    } | body.template_context
    settings = get_plugin_settings(request.app)

    try:
        info = await check_email_server_responsiveness(settings)

        message = await send_email_from_template(
            request,
            from_=body.from_ or product.support_email,
            to=body.to,
            template=template_path,
            context=context,
        )

        return envelope_json_response(
            TestPassed(
                fixtures=body.dict(),
                info={
                    "email-server": info,
                    "message": message.items(),
                },
            )
        )

    except Exception as err:  # pylint: disable=broad-except
        logger.exception(
            "test_email failed for %s",
            f"{settings.json(indent=1)}",
        )
        return envelope_json_response(
            TestFailed.create_from_exception(error=err, test_name="test_email")
        )
