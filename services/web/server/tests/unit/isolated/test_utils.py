import asyncio
import contextlib
import time
import urllib.parse
from datetime import datetime

from simcore_service_webserver.utils import (
    DATETIME_FORMAT,
    compose_support_error_msg,
    get_task_info,
    now_str,
    to_datetime,
)
from yarl import URL


def test_yarl_new_url_generation():
    base_url_with_autoencode = URL("http://director:8001/v0", encoded=False)
    service_key = "simcore/services/dynamic/smash"
    service_version = "1.0.3"

    # NOTE: careful, first we need to encode the "/" in this file path.
    # For that we need safe="" option
    assert urllib.parse.quote("/") == "/"
    assert urllib.parse.quote("/", safe="") == "%2F"
    assert urllib.parse.quote("%2F", safe="") == "%252F"

    quoted_service_key = urllib.parse.quote(service_key, safe="")

    # Since 1.6.x composition using '/' creates URLs with auto-encoding enabled by default
    assert (
        str(
            base_url_with_autoencode / "services" / quoted_service_key / service_version
        )
        == "http://director:8001/v0/services/simcore%252Fservices%252Fdynamic%252Fsmash/1.0.3"
    )

    # Passing encoded=True parameter prevents URL auto-encoding, user is responsible about URL correctness
    url_without_autoencode = URL(
        f"http://director:8001/v0/services/{quoted_service_key}/1.0.3", encoded=True
    )

    assert (
        str(url_without_autoencode)
        == "http://director:8001/v0/services/simcore%2Fservices%2Fdynamic%2Fsmash/1.0.3"
    )


def test_time_utils():
    snapshot0 = now_str()

    time.sleep(0.5)
    snapshot1 = now_str()

    now0 = to_datetime(snapshot0)
    now1 = to_datetime(snapshot1)
    assert now0 < now1

    # tests biyective
    now_time = datetime.utcnow()
    snapshot = now_time.strftime(DATETIME_FORMAT)
    assert now_time == datetime.strptime(snapshot, DATETIME_FORMAT)


def test_compose_support_error_msg():

    msg = compose_support_error_msg(
        "first sentence for Mr.X   \n  Second sentence.",
        error_code="OEC:139641204989600",
        support_email="support@email.com",
    )
    assert (
        msg == "First sentence for Mr.X. Second sentence."
        " For more information please forward this message to support@email.com (supportID=OEC:139641204989600)"
    )


async def test_get_task_info():
    """Test get_task_info function with asyncio tasks"""

    async def dummy_task():
        await asyncio.sleep(0.1)
        return "task_result"

    # Create a named task
    task = asyncio.create_task(dummy_task(), name="test_task")

    task_info = get_task_info(task)

    # Check that task_info is a dictionary
    assert isinstance(task_info, dict)

    # Check that it contains expected keys from TaskInfoDict
    expected_keys = {"txt", "type", "done", "cancelled", "stack", "exception"}
    assert all(key in task_info for key in expected_keys)

    # Check basic types
    assert isinstance(task_info["txt"], str)
    assert isinstance(task_info["type"], str)
    assert isinstance(task_info["done"], bool)
    assert isinstance(task_info["cancelled"], bool)
    assert isinstance(task_info["stack"], list)

    # Check that task name is in the txt representation
    assert "test_task" in task_info["txt"]

    # Check that stack contains frame info when task is running
    if not task_info["done"]:
        assert len(task_info["stack"]) > 0
        # Check stack frame structure
        for frame_info in task_info["stack"]:
            assert "f_code" in frame_info
            assert "f_lineno" in frame_info
            assert isinstance(frame_info["f_code"], str)
            assert isinstance(frame_info["f_lineno"], str)

    # Clean up
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


async def test_get_task_info_unnamed_task():
    """Test get_task_info function with unnamed tasks"""

    async def dummy_task():
        await asyncio.sleep(0.1)

    # Create an unnamed task
    task = asyncio.create_task(dummy_task())

    task_info = get_task_info(task)

    # Check basic structure
    assert isinstance(task_info, dict)
    expected_keys = {"txt", "type", "done", "cancelled", "stack", "exception"}
    assert all(key in task_info for key in expected_keys)

    # Check that txt contains task representation
    assert isinstance(task_info["txt"], str)
    assert "Task" in task_info["txt"]

    # Clean up
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
