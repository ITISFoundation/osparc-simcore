import re

import pytest
from aioresponses import aioresponses as AioResponsesMock
from servicelib.aiohttp import status
from simcore_service_storage.modules.datcore_adapter.datcore_adapter_settings import (
    DatcoreAdapterSettings,
)


@pytest.fixture
def datcore_adapter_service_mock(
    aioresponses_mocker: AioResponsesMock,
) -> AioResponsesMock:
    dat_core_settings = DatcoreAdapterSettings.create_from_envs()
    datcore_adapter_base_url = dat_core_settings.endpoint
    # mock base endpoint
    aioresponses_mocker.get(
        datcore_adapter_base_url, status=status.HTTP_200_OK, repeat=True
    )
    list_datasets_re = re.compile(rf"^{datcore_adapter_base_url}/datasets")
    aioresponses_mocker.get(list_datasets_re, status=status.HTTP_200_OK, repeat=True)
    aioresponses_mocker.get(
        datcore_adapter_base_url, status=status.HTTP_200_OK, repeat=True, payload={}
    )
    return aioresponses_mocker
