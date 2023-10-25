import logging

from aiohttp import web
from pydantic import EmailStr, PositiveInt

from ..email.utils import send_email_from_template
from ..products.api import get_current_product, get_product_template_path

_logger = logging.getLogger(__name__)


async def send_close_account_email(
    request: web.Request,
    user_email: EmailStr,
    user_name: str,
    retention_days: PositiveInt = 30,
):
    template_name = "close_account.jinja2"
    email_template_path = await get_product_template_path(request, template_name)
    product = get_current_product(request)

    try:
        await send_email_from_template(
            request,
            from_=product.support_email,
            to=user_email,
            template=email_template_path,
            context={
                "host": request.host,
                "name": user_name.capitalize(),
                "support_email": product.support_email,
                "retention_days": retention_days,
            },
        )
    except Exception:  # pylint: disable=broad-except
        _logger.exception(
            "Failed while sending '%s' email to %s",
            template_name,
            f"{user_email=}",
        )
