# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio

import pytest
import pytest_asyncio

pytest_simcore_core_services_selection = [
    "migration",
    "postgres",
]
pytest_simcore_ops_services_selection = []


@pytest.fixture(autouse=True)
def _drop_and_recreate_postgres(database_from_template_before_each_function: None):
    return


@pytest.fixture
def some_fixture(
    event_loop: asyncio.AbstractEventLoop,
    simcore_services_ready: None,
):
    event_loop.run_until_complete(asyncio.sleep(0.1))


# NOTE: Remove skip marker to check whether `pytest-asyncio<0.23` constraint in _test.in
@pytest.mark.skip(reason="Checks pytest-asyncio upgrade issue")
async def test_pytest_asyncio_known_issue(some_fixture: None):
    #
    # This test demonstrates a common failure in most integration tests when using pytest-asyncio version 0.23.
    # The test was derived by simplifying the original test_garbage_collection.py to highlight the issue.
    #
    # Due to an unresolved issue in pytest-asyncio, pytest will fail to execute this async test,
    # resulting in the following error:
    #
    #  `RuntimeError: There is no current event loop in thread 'MainThread'.`
    #
    # For more details, refer to the "Known Issues" section in the release notes:
    # https://github.com/pytest-dev/pytest-asyncio/releases/tag/v0.23.8
    #

    assert pytest_asyncio.__version__

    # NOTE: it might fail upon db tear-down but it is not relevant for this test
