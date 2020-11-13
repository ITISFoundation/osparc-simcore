import re

import pytest
from aioresponses import aioresponses
from models_library.nodes import RunningState


@pytest.fixture
async def director_v2_subsystem_mock() -> aioresponses:
    """uses aioresponses to mock all calls of an aiohttpclient
    WARNING: any request done through the client will go through aioresponses. It is
    unfortunate but that means any valid request (like calling the test server) prefix must be set as passthrough.
    Other than that it seems to behave nicely
    """
    PASSTHROUGH_REQUESTS_PREFIXES = ["http://127.0.0.1", "ws://"]
    pattern = re.compile(r"^http://[a-z\-_]*director-v2:[0-9]+/v2/computations/.*$")
    with aioresponses(passthrough=PASSTHROUGH_REQUESTS_PREFIXES) as mock:
        mock.get(
            pattern,
            status=202,
            payload={"state": str(RunningState.NOT_STARTED.value)},
            repeat=True,
        )

        yield mock
