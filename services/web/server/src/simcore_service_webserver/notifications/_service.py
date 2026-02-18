from dataclasses import asdict
from typing import Any

from aiohttp import web
from celery_library.async_jobs import submit_job
from common_library.network import NO_REPLY_LOCAL, replace_email_parts
from models_library.api_schemas_async_jobs.async_jobs import AsyncJobGet
from models_library.groups import GroupID
from models_library.notifications import ChannelType, TemplatePreview, TemplateRef
from models_library.notifications_errors import (
    NotificationsNoActiveRecipientsError,
    NotificationsUnsupportedChannelError,
)
from models_library.products import ProductName
from models_library.rpc.notifications.template import (
    TemplatePreviewRpcRequest,
    TemplateRefRpc,
)
from models_library.users import UserID
from servicelib.celery.models import ExecutionMetadata, OwnerMetadata
from servicelib.rabbitmq.rpc_interfaces.notifications.notifications_templates import (
    preview_template as remote_preview_template,
)

from ..celery import get_task_manager
from ..models import WebServerOwnerMetadata
from ..products import products_service
from ..rabbitmq import get_rabbitmq_rpc_client
from ..users import users_service
from ._helpers import get_product_data
from ._models import Contact, EmailContact, EmailContent, EmailNotificationMessage


def _get_user_display_name(user: dict) -> str:
    first_name = user.get("first_name") or ""
    last_name = user.get("last_name") or ""
    return f"{first_name} {last_name}".strip()


async def _collect_active_recipients(app: web.Application, group_ids: list[GroupID]) -> list[EmailContact]:
    # Collect all unique user IDs from all groups
    all_user_ids: set[UserID] = set()
    for group_id in group_ids:
        user_ids = await users_service.get_users_in_group(app, gid=group_id)
        all_user_ids.update(user_ids)

    active_users = await users_service.get_active_users_email_data(app, user_ids=list(all_user_ids))

    # Deduplicate by email address while preserving order
    recipients_dict: dict[str, EmailContact] = {}
    for user in active_users:
        email_addr = EmailContact(
            name=_get_user_display_name(user),
            email=user["email"],
        )
        recipients_dict[user["email"]] = email_addr

    return list(recipients_dict.values())


async def _create_email_message(
    app: web.Application,
    *,
    product_name: ProductName,
    group_ids: list[GroupID] | None,
    external_contacts: list[Contact] | None,
    content: dict[str, Any],
) -> EmailNotificationMessage:
    product = products_service.get_product(app, product_name)

    from_ = EmailContact(
        name=product.display_name,
        email=replace_email_parts(
            product.support_email,
            new_local=NO_REPLY_LOCAL,
        ),
    )

    to: list[EmailContact] = []

    if group_ids:
        to = await _collect_active_recipients(app, group_ids=group_ids)

    if external_contacts:
        to.extend(external_contacts)

    if not to:
        raise NotificationsNoActiveRecipientsError

    email_content = EmailContent(**content)

    return EmailNotificationMessage(
        from_=from_,
        to=to,
        content=email_content,
    )


async def preview_template(
    app: web.Application,
    *,
    product_name: ProductName,
    ref: TemplateRef,
    context: dict[str, Any],
) -> TemplatePreview:
    product_data = get_product_data(app, product_name=product_name)

    enriched_context = {**context, "product": asdict(product_data)}

    request = TemplatePreviewRpcRequest(
        ref=TemplateRefRpc(**ref.model_dump()),
        context=enriched_context,
    )

    preview = await remote_preview_template(
        get_rabbitmq_rpc_client(app),
        request=request,
    )

    return TemplatePreview(**preview.model_dump())


async def send_message(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    channel: ChannelType,
    group_ids: list[GroupID] | None,
    external_contacts: list[Contact] | None,
    content: dict[str, Any],  # NOTE: validated internally
) -> AsyncJobGet:
    match channel:
        case ChannelType.email:
            message = await _create_email_message(
                app,
                product_name=product_name,
                group_ids=group_ids,
                external_contacts=external_contacts,
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
