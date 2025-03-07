import re
from collections.abc import Iterator

import pytest
import respx
from faker import Faker
from fastapi_pagination import LimitOffsetParams, create_page
from servicelib.aiohttp import status
from simcore_service_storage.modules.datcore_adapter.datcore_adapter_settings import (
    DatcoreAdapterSettings,
)


@pytest.fixture
def datcore_adapter_service_mock(faker: Faker) -> Iterator[respx.MockRouter]:
    dat_core_settings = DatcoreAdapterSettings.create_from_envs()
    datcore_adapter_base_url = dat_core_settings.endpoint
    # mock base endpoint
    with respx.mock(
        base_url=datcore_adapter_base_url,
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mocker:
        respx_mocker.get(
            datcore_adapter_base_url,
            name="healthcheck",
        ).respond(status.HTTP_200_OK)
        respx_mocker.get(
            f"{datcore_adapter_base_url}/user/profile", name="get_user_profile"
        ).respond(status.HTTP_200_OK, json=faker.pydict(allowed_types=(str,)))
        list_datasets_re = re.compile(rf"^{datcore_adapter_base_url}/datasets")
        respx_mocker.get(list_datasets_re, name="list_datasets").respond(
            status.HTTP_200_OK,
            json=create_page([], 0, LimitOffsetParams()),
        )
        respx_mocker.get(datcore_adapter_base_url, name="base_endpoint").respond(
            status.HTTP_200_OK, json={}
        )
        yield respx_mocker
