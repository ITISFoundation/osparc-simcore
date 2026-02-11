from aiohttp import web
from celery_library.async_jobs import submit_job
from common_library.network import NO_REPLY_LOCAL, replace_email_parts
from models_library.api_schemas_async_jobs.async_jobs import AsyncJobGet
from models_library.groups import GroupID
from models_library.notifications import ChannelType
from models_library.notifications_errors import (
    NotificationsNoActiveRecipientsError,
    NotificationsUnsupportedChannelError,
)
from models_library.products import ProductName
from models_library.users import UserID
from pydantic import BaseModel
from servicelib.celery.models import ExecutionMetadata, OwnerMetadata

from ..celery import get_task_manager
from ..models import WebServerOwnerMetadata
from ..products import products_service
from ._models import EmailAddress, EmailContent, EmailNotificationMessage


def _get_user_display_name(user: dict) -> str:
    first_name = user.get("first_name") or ""
    last_name = user.get("last_name") or ""
    return f"{first_name} {last_name}".strip()


async def _collect_active_recipients(app: web.Application, recipient_groups: list[GroupID]) -> list[EmailAddress]:
    from ..users import users_service  # noqa: PLC0415

    # Collect all unique user IDs from all groups
    all_user_ids: set[UserID] = set()
    for group_id in recipient_groups:
        user_ids = await users_service.get_users_in_group(app, gid=group_id)
        all_user_ids.update(user_ids)

    active_users = await users_service.get_active_users_email_data(app, user_ids=list(all_user_ids))

    # Deduplicate by email address while preserving order
    recipients_dict: dict[str, EmailAddress] = {}
    for user in active_users:
        email_addr = EmailAddress(
            name=_get_user_display_name(user),
            email=user["email"],
        )
        recipients_dict[user["email"]] = email_addr

    return list(recipients_dict.values())


async def _create_email_message(
    app: web.Application,
    *,
    product_name: ProductName,
    recipients: list[GroupID],
    content: BaseModel,
) -> EmailNotificationMessage:
    product = products_service.get_product(app, product_name)

    from_ = EmailAddress.from_email_str(replace_email_parts(product.support_email, new_local=NO_REPLY_LOCAL))

    to = await _collect_active_recipients(app, recipients)
    if not to:
        raise NotificationsNoActiveRecipientsError

    email_content = EmailContent(**content.model_dump())

    return EmailNotificationMessage(
        from_=from_,
        to=to,
        content=email_content,
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
    match channel:
        case ChannelType.email:
            message = await _create_email_message(
                app,
                product_name=product_name,
                recipients=recipients,
                content=content,
            )
        case _:
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
