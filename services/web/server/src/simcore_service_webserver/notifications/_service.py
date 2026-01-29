from aiohttp import web
from celery_library.async_jobs import submit_job
from models_library.api_schemas_async_jobs.async_jobs import AsyncJobGet
from models_library.groups import GroupID
from models_library.notifications import ChannelType
from models_library.notifications_errors import NotificationsUnsupportedChannelError
from models_library.products import ProductName
from models_library.users import UserID
from pydantic import BaseModel
from servicelib.celery.models import ExecutionMetadata, OwnerMetadata

from ..celery import get_task_manager
from ..models import WebServerOwnerMetadata
from ..products.products_service import get_product
from ._models import EmailAddress, EmailContent, EmailNotificationMessage


async def _create_email_message(
    app: web.Application,
    *,
    product_name: ProductName,
    channel: ChannelType,
    recipients: list[GroupID],
    content: BaseModel,
) -> EmailNotificationMessage:
    from ..users.users_service import get_user, get_users_in_group  # noqa: PLC0415

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
        raise NotificationsUnsupportedChannelError(channel=channel)

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
