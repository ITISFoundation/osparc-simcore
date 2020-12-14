import re

import pytest
from aioresponses import aioresponses
from aioresponses.core import CallbackResult
from models_library.projects_state import RunningState
from yarl import URL


def creation_cb(url, **kwargs) -> CallbackResult:

    assert "json" in kwargs, f"missing body in call to {url}"
    body = kwargs["json"]
    for param in ["user_id", "project_id"]:
        assert param in body, f"{param} is missing from body: {body}"
    state = (
        RunningState.PUBLISHED
        if "start_pipeline" in body and body["start_pipeline"]
        else RunningState.NOT_STARTED
    )

    return CallbackResult(
        status=201, payload={"id": kwargs["json"]["project_id"], "state": state}
    )


@pytest.fixture
async def director_v2_service_mock() -> aioresponses:

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


@pytest.fixture
async def storage_v0_service_mock() -> aioresponses:

    """uses aioresponses to mock all calls of an aiohttpclient
    WARNING: any request done through the client will go through aioresponses. It is
    unfortunate but that means any valid request (like calling the test server) prefix must be set as passthrough.
    Other than that it seems to behave nicely
    """
    PASSTHROUGH_REQUESTS_PREFIXES = ["http://127.0.0.1", "ws://"]

    def get_download_link_cb(url: URL, **kwargs) -> CallbackResult:
        file_id = url.path.rsplit("/files/")[1]

        return CallbackResult(
            status=200, payload={"data": {"link": f"file://{file_id}"}}
        )

    get_download_link_pattern = re.compile(
        r"^http://[a-z\-_]*storage:[0-9]+/v0/locations/[0-9]+/files/.+$"
    )

    get_locations_link_pattern = re.compile(
        r"^http://[a-z\-_]*storage:[0-9]+/v0/locations.*$"
    )

    with aioresponses(passthrough=PASSTHROUGH_REQUESTS_PREFIXES) as mock:
        mock.get(get_download_link_pattern, callback=get_download_link_cb, repeat=True)
        mock.get(
            get_locations_link_pattern,
            status=200,
            payload={"data": [{"name": "simcore.s3", "id": "0"}]},
        )
        yield mock
