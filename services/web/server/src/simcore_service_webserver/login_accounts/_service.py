import asyncio
import logging
from io import BytesIO
from typing import Any

from aiohttp import web
from captcha.image import ImageCaptcha
from models_library.emails import LowerCaseEmailStr
from models_library.notifications import Channel
from models_library.products import ProductName
from models_library.users import UserID
from models_library.utils.fastapi_encoders import jsonable_encoder
from PIL.Image import Image
from pydantic import EmailStr, PositiveInt, TypeAdapter, ValidationError
from servicelib.utils_secrets import generate_passcode

from ..notifications._models import EmailContact
from ..notifications._service import send_message_from_template
from ..products.models import Product
from ..users import _accounts_service
from ..users.schemas import UserAccountRestPreRegister

_logger = logging.getLogger(__name__)


async def send_close_account_email(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    user_email: EmailStr,
    user_first_name: str,
    retention_days: PositiveInt,
    host: str,
):
    try:
        await send_message_from_template(
            app,
            user_id=user_id,
            product_name=product_name,
            channel=Channel.email,
            group_ids=None,
            external_contacts=[EmailContact(name=user_first_name, email=user_email)],
            template_name="unregister",
            context={
                "host": host,
                "user": {
                    "first_name": user_first_name.capitalize(),
                    "user_name": user_first_name,
                },
                "retention_days": retention_days,
            },
        )
    except Exception:  # pylint: disable=broad-except
        _logger.exception(
            "Failed while sending 'unregister' email to %s",
            f"{user_email=}",
        )


async def send_account_request_email_to_support(
    app: web.Application,
    *,
    product_name: ProductName,
    product: Product,
    request_form: dict[str, Any],
    ipinfo: dict,
    host: str,
):
    destination_email = product.product_owners_email or product.support_email
    reply_to_email: LowerCaseEmailStr | None
    try:
        reply_to_email = TypeAdapter(LowerCaseEmailStr).validate_python(request_form.get("email"))
    except ValidationError:
        reply_to_email = None

    reply_to_contact = EmailContact(name="", email=reply_to_email) if reply_to_email else None

    try:
        await send_message_from_template(
            app,
            user_id=None,
            product_name=product_name,
            channel=Channel.email,
            group_ids=None,
            external_contacts=[EmailContact(name="", email=destination_email)],
            reply_to=reply_to_contact,
            template_name="account_requested",
            context={
                "host": host.rstrip("/"),
                "product_info": jsonable_encoder(
                    product.model_dump(
                        include={
                            "name",
                            "display_name",
                            "vendor",
                            "is_payment_enabled",
                        }
                    )
                ),
                "request_form": request_form,
                "ipinfo": ipinfo,
            },
        )
    except Exception:  # pylint: disable=broad-except
        _logger.exception(
            "Failed while sending 'account_requested' email to %s",
            f"{destination_email=}",
        )


async def create_captcha() -> tuple[str, bytes]:
    def _run() -> tuple[str, bytes]:
        captcha_text = generate_passcode(number_of_digits=6)
        image = ImageCaptcha(width=140, height=45)

        # Generate image
        data: Image = image.create_captcha_image(chars=captcha_text, color=(221, 221, 221), background=(0, 20, 46))

        img_byte_arr = BytesIO()
        data.save(img_byte_arr, format="PNG")
        image_data = img_byte_arr.getvalue()

        return (captcha_text, image_data)

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _run)


async def create_pre_registration(
    app: web.Application,
    *,
    profile: UserAccountRestPreRegister,
    product_name: ProductName,
):
    await _accounts_service.pre_register_user(app, profile=profile, creator_user_id=None, product_name=product_name)
