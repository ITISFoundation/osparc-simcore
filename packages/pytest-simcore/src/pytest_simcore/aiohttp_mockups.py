import re
from aioresponses.core import CallbackResult

import pytest
from aioresponses import aioresponses
from models_library.nodes import RunningState


def creation_cb(url, **kwargs):
    assert "json" in kwargs, f"missing body in call to {url}"
    body = kwargs["json"]
    for param in ["user_id", "project_id"]:
        assert param in body, f"{param} is missing from body: {body}"

    return CallbackResult(status=201, payload={"id": kwargs["json"]["project_id"]})


@pytest.fixture
async def director_v2_subsystem_mock() -> aioresponses:
    """uses aioresponses to mock all calls of an aiohttpclient
    WARNING: any request done through the client will go through aioresponses. It is
    unfortunate but that means any valid request (like calling the test server) prefix must be set as passthrough.
    Other than that it seems to behave nicely
    """
    PASSTHROUGH_REQUESTS_PREFIXES = ["http://127.0.0.1", "ws://"]
    create_computation_pattern = re.compile(
        r"^http://[a-z\-_]*director-v2:[0-9]+/v2/computations$"
    )

    get_computation_pattern = re.compile(
        r"^http://[a-z\-_]*director-v2:[0-9]+/v2/computations/.*$"
    )
    stop_computation_pattern = re.compile(
        r"^http://[a-z\-_]*director-v2:[0-9]+/v2/computations/.*:stop$"
    )
    delete_computation_pattern = get_computation_pattern
    with aioresponses(passthrough=PASSTHROUGH_REQUESTS_PREFIXES) as mock:
        mock.post(
            create_computation_pattern,
            callback=creation_cb,
            repeat=True,
        )
        mock.post(
            stop_computation_pattern,
            status=204,
            repeat=True,
        )
        mock.get(
            get_computation_pattern,
            status=202,
            payload={"state": str(RunningState.NOT_STARTED.value)},
            repeat=True,
        )
        mock.delete(delete_computation_pattern, status=204, repeat=True)

        yield mock
