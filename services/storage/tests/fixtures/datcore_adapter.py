import pytest
from aiohttp import web
from aioresponses import aioresponses as AioResponsesMock
from simcore_service_storage.settings import Settings


@pytest.fixture
def datcore_adapter_service_mock(
    app_settings: Settings,
    aioresponses_mocker: AioResponsesMock,
) -> AioResponsesMock:
    datcore_adapter_base_url = app_settings.DATCORE_ADAPTER.endpoint
    # mock base endpoint
    aioresponses_mocker.get(
        datcore_adapter_base_url, status=web.HTTPOk.status_code, repeat=True
    )
    return aioresponses_mocker
