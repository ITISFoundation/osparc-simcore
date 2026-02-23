from typing import Any, Final

from ..models import ExecutionMetadata, GroupUUID, OwnerMetadata, TaskName, TaskUUID
from ..task_manager import TaskManager

SEND_MESSAGE_TASK_NAME_TEMPLATE: Final[TaskName] = "send_{}_message"


async def submit_send_message_task(
    task_manager: TaskManager,
    *,
    owner_metadata: OwnerMetadata,
    message: dict[str, Any],  # NOTE: validated internally
) -> tuple[TaskUUID, TaskName]:
    return await task_manager.submit_task(
        ExecutionMetadata(
            name=SEND_MESSAGE_TASK_NAME_TEMPLATE.format(message["channel"]),
            queue="notifications",
        ),
        owner_metadata=owner_metadata,
        message=message,
    ), SEND_MESSAGE_TASK_NAME_TEMPLATE.format(message["channel"])


async def submit_send_messages_task(
    task_manager: TaskManager,
    *,
    owner_metadata: OwnerMetadata,
    messages: list[dict[str, Any]],  # NOTE: validated internally
) -> tuple[GroupUUID, list[TaskUUID], TaskName]:
    return await task_manager.submit_group(
        [
            (
                ExecutionMetadata(
                    name=SEND_MESSAGE_TASK_NAME_TEMPLATE.format(message["channel"]),
                    queue="notifications",
                ),
                message,
            )
            for message in messages
        ],
        owner_metadata=owner_metadata,
    ) + (SEND_MESSAGE_TASK_NAME_TEMPLATE.format(messages[0]["channel"]),)
