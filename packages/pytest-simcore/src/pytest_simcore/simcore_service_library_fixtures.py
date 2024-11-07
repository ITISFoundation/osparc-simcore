from collections.abc import AsyncIterable

import pytest
from servicelib.async_utils import cancel_sequential_workers


@pytest.fixture
async def ensure_run_in_sequence_context_is_empty() -> AsyncIterable[None]:
    """
    Needed in tests calling functions decorated with 'run_sequentially_in_context'

    This is a teardown only fixture

    Required when shutting down the application or ending tests
    otherwise errors will occur when closing the loop
    """

    # nothing on-startup

    yield

    await cancel_sequential_workers()
