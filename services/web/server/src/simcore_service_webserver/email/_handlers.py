import logging
from typing import Any, Literal

from aiohttp import web
from models_library.emails import LowerCaseEmailStr
from pydantic import BaseModel, Field
from servicelib.aiohttp.requests_validation import parse_request_body_as
from servicelib.logging_errors import create_troubleshootting_log_kwargs

from .._meta import API_VTAG
from ..login.decorators import login_required
from ..products import products_web
from ..products.models import Product
from ..security.decorators import permission_required
from ..utils_aiohttp import envelope_json_response
from ._core import check_email_server_responsiveness, send_email_from_template
from .settings import get_plugin_settings

_logger = logging.getLogger(__name__)


class TestEmail(BaseModel):
    from_: LowerCaseEmailStr | None = Field(None, description="Email sender")
    to: LowerCaseEmailStr = Field(..., description="Email receiver")
    template_name: Literal[
        "change_email_email.jinja2",
        "new_2fa_code.jinja2",
        "registration_email.jinja2",
        "reset_password_email.jinja2",
        "service_submission.jinja2",
    ] = "registration_email.jinja2"
    template_context: dict[str, Any] = {}


class EmailTestFailed(BaseModel):
    test_name: str
    error_code: str | None = None
    user_message: str = "Email test failed"


class EmailTestPassed(BaseModel):
    fixtures: dict[str, Any]
    info: dict[str, Any]


routes = web.RouteTableDef()


@routes.post(f"/{API_VTAG}/email:test", name="test_email")
@login_required
@permission_required("admin.*")
async def test_email(request: web.Request):
    """Tests email by rendering and sending a template email to some address destination"""

    body = await parse_request_body_as(TestEmail, request)

    product: Product = products_web.get_current_product(request)

    template_path = await products_web.get_product_template_path(
        request, filename=body.template_name
    )

    context = {
        "host": request.host,
        "link": "https://httpbin.org/redirect-to?url=https%3A%2F%2Fhttpbin.org%2F",
        "name": "Mr. Smith",
        "support_email": product.support_email,
        "product": product,
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
            EmailTestPassed(
                fixtures=body.model_dump(),
                info={
                    "email-server": info,
                    "email-headers": message.items(),
                },
            )
        )

    except Exception as err:  # pylint: disable=broad-except

        _logger.exception(
            **create_troubleshootting_log_kwargs(
                user_error_msg="Email test failed",
                error=err,
                error_context={
                    "template_name": body.template_name,
                    "to": body.to,
                    "from_": body.from_ or product.support_email,
                    "settings": settings.model_dump(),
                },
                tip="Check SMTP settings and network connectivity",
            )
        )
        return envelope_json_response(
            EmailTestFailed(
                test_name="test_email",
                error_code=getattr(err, "error_code", None),
                user_message="Email test failed. Please check the logs for more details.",
            )
        )
