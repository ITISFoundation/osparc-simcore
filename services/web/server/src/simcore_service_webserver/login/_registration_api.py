import functools
import logging
from io import BytesIO
from typing import Any

from aiohttp import web
from captcha.image import ImageCaptcha
from common_library.json_serialization import json_dumps
from models_library.emails import LowerCaseEmailStr
from models_library.utils.fastapi_encoders import jsonable_encoder
from PIL.Image import Image
from pydantic import EmailStr, PositiveInt, TypeAdapter, ValidationError
from servicelib.utils_secrets import generate_passcode

from ..email.utils import send_email_from_template
from ..products.api import Product, get_current_product, get_product_template_path

_logger = logging.getLogger(__name__)


async def send_close_account_email(
    request: web.Request,
    user_email: EmailStr,
    user_first_name: str,
    retention_days: PositiveInt,
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
                "name": user_first_name.capitalize(),
                "support_email": product.support_email,
                "retention_days": retention_days,
                "product": product,
            },
        )
    except Exception:  # pylint: disable=broad-except
        _logger.exception(
            "Failed while sending '%s' email to %s",
            template_name,
            f"{user_email=}",
        )


def _json_encoder_and_dumps(obj: Any, **kwargs):
    # NOTE: equivalent json.dumps(obj, default=jsonable_encode(pydantic_encoder(.))
    return json_dumps(jsonable_encoder(obj), **kwargs)


async def send_account_request_email_to_support(
    request: web.Request,
    *,
    product: Product,
    request_form: dict[str, Any],
    ipinfo: dict,
):
    template_name = "request_account.jinja2"
    support_email = product.support_email
    email_template_path = await get_product_template_path(request, template_name)
    try:
        user_email = TypeAdapter(LowerCaseEmailStr).validate_python(
            request_form.get("email", None)
        )
    except ValidationError:
        user_email = None

    try:
        await send_email_from_template(
            request,
            from_=support_email,
            to=support_email,
            reply_to=user_email,  # So that issue-tracker system ACK email is sent to the user that requests the account
            template=email_template_path,
            context={
                "host": request.host,
                "name": "support-team",
                "product": product.model_dump(
                    include={
                        "name",
                        "display_name",
                        "vendor",
                        "is_payment_enabled",
                    }
                ),
                "request_form": request_form,
                "ipinfo": ipinfo,
                "dumps": functools.partial(_json_encoder_and_dumps, indent=1),
            },
        )
    except Exception:  # pylint: disable=broad-except
        _logger.exception(
            "Failed while sending '%s' email to %s",
            template_name,
            f"{support_email=}",
        )


async def generate_captcha() -> tuple[str, bytes]:
    captcha_text = generate_passcode(number_of_digits=6)
    image = ImageCaptcha(width=140, height=45)

    # Generate image
    data: Image = image.create_captcha_image(
        chars=captcha_text, color=(221, 221, 221), background=(0, 20, 46)
    )

    img_byte_arr = BytesIO()
    data.save(img_byte_arr, format="PNG")
    image_data = img_byte_arr.getvalue()

    return (captcha_text, image_data)
