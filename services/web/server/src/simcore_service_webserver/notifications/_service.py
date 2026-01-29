from aiohttp import web
from celery_library.async_jobs import submit_job
from models_library.api_schemas_async_jobs.async_jobs import AsyncJobGet
from models_library.emails import LowerCaseEmailStr
from models_library.groups import GroupID
from models_library.notifications import ChannelType
from models_library.products import ProductName
from models_library.users import UserID
from notifications_library._models import ProductData, ProductUIData, UserData
from pydantic import BaseModel
from servicelib.celery.models import ExecutionMetadata, OwnerMetadata

from ..celery import get_task_manager
from ..models import WebServerOwnerMetadata
from ..notifications._models import EmailAddress, EmailContent, EmailNotificationMessage
from ..products._service import get_product
from ..users._users_service import get_user, get_users_in_group


def get_product_data(
    app: web.Application,
    *,
    product_name: ProductName,
) -> ProductData:
    product = get_product(app, product_name=product_name)

    # Extract vendor information
    vendor_display_inline = (
        str(product.vendor.get("name"))
        if product.vendor and product.vendor.get("name") is not None
        else "IT'IS Foundation"
    )

    # Extract UI information from product.vendor.ui (optional)
    ui_data = ProductUIData(
        logo_url=(product.vendor.get("ui", {}).get("logo_url") if product.vendor else None),
        strong_color=(product.vendor.get("ui", {}).get("strong_color") if product.vendor else None),
    )

    homepage_url = product.vendor.get("url") if product.vendor else None

    return ProductData(
        product_name=product_name,
        display_name=product.display_name,
        vendor_display_inline=vendor_display_inline,
        support_email=product.support_email,
        homepage_url=homepage_url,
        ui=ui_data,
    )


def create_user_data(
    *,
    user_email: LowerCaseEmailStr,
    first_name: str,
    last_name: str,
) -> UserData:
    return UserData(
        user_name=f"{first_name} {last_name}".strip(),
        email=user_email,
        first_name=first_name,
        last_name=last_name,
    )


async def _create_email_message(
    app: web.Application,
    *,
    product_name: ProductName,
    channel: ChannelType,
    recipients: list[GroupID],
    content: BaseModel,
) -> EmailNotificationMessage:
    to: set[EmailAddress] = set()

    product = get_product(app, product_name)

    for recipient in recipients:
        u_ids = await get_users_in_group(app, gid=recipient)
        for u_id in u_ids:
            user = await get_user(app, user_id=u_id)
            to.add(
                EmailAddress(
                    display_name=user["first_name"] or user["email"],
                    addr_spec=user["email"],
                )
            )

    return EmailNotificationMessage(
        channel=channel,
        from_=EmailAddress(
            display_name=product.display_name,
            addr_spec=product.support_email,
        ),
        to=list(to),
        content=EmailContent(**content.model_dump()),
    )


async def send_message(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    channel: ChannelType,
    recipients: list[GroupID],
    content: BaseModel,
) -> AsyncJobGet:
    # Dispatch to the appropriate message creator based on channel type
    if channel == ChannelType.email:
        message = await _create_email_message(
            app,
            product_name=product_name,
            channel=channel,
            recipients=recipients,
            content=content,
        )
    else:
        msg = f"Unsupported channel type: {channel}"
        raise NotImplementedError(msg)

    return await submit_job(
        get_task_manager(app),
        execution_metadata=ExecutionMetadata(name=f"send_{channel}", queue="notifications"),
        owner_metadata=OwnerMetadata.model_validate(
            WebServerOwnerMetadata(
                user_id=user_id,
                product_name=product_name,
            ).model_dump()
        ),
        message=message.model_dump(),
    )
