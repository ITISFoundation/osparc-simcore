from collections.abc import AsyncIterable

import pytest
from servicelib.async_utils import _sequential_jobs_contexts


@pytest.fixture
async def ensure_run_in_sequence_context_is_empty() -> AsyncIterable[None]:
    """
    Needed in tests calling functions decorated with 'run_sequentially_in_context'

    This is a teardown only fixture

    Required when shutting down the application or ending tests
    otherwise errors will occur when closing the loop
    """

    # nothing on-startup
    assert (
        len(_sequential_jobs_contexts) == 0
    ), "Not all contexts were cleaned up on startup"

    yield

    assert (
        len(_sequential_jobs_contexts) == 0
    ), "Not all contexts were cleaned up on teardown"
