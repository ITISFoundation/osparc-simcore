import pytest
from aioresponses import aioresponses as AioResponsesMock

PASSTHROUGH_REQUESTS_PREFIXES = ["http://127.0.0.1", "ws://"]


@pytest.fixture
def aioresponses_mocker() -> AioResponsesMock:
    """Generick aioresponses mock

    SEE https://github.com/pnuckowski/aioresponses

    Usage

        async def test_this(aioresponses_mocker):
            aioresponses_mocker.get("https://foo.io")

            async with aiohttp.ClientSession() as session:
                async with session.get("https://foo.io") as response:
                    assert response.status == 200
    """
    with AioResponsesMock(passthrough=PASSTHROUGH_REQUESTS_PREFIXES) as mock:
        yield mock
