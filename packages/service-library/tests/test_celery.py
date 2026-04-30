# pylint: disable=redefined-outer-name
# pylint: disable=protected-access

import inspect

from servicelib.celery.task_manager import TaskManager


def test_task_manager_protocol_has_plain_owner_params():
    """Verify the TaskManager protocol uses plain owner/user_id/product_name params."""

    sig = inspect.signature(TaskManager.submit_task)
    assert "owner" in sig.parameters
    assert "user_id" in sig.parameters
    assert "product_name" in sig.parameters

    sig = inspect.signature(TaskManager.list_tasks)
    assert "owner" in sig.parameters
    assert "user_id" in sig.parameters
    assert "product_name" in sig.parameters

    sig = inspect.signature(TaskManager.cancel)
    # cancel should NOT have owner params
    assert "owner" not in sig.parameters
    assert "user_id" not in sig.parameters
