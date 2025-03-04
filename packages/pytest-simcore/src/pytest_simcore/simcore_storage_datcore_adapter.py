import re
from collections.abc import Iterator

import pytest
import respx
from faker import Faker
from fastapi_pagination import Page, Params
from pytest_simcore.helpers.host import get_localhost_ip
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
        # NOTE: passthrough the locahost and the local ip
        respx_mocker.route(host="127.0.0.1").pass_through()
        respx_mocker.route(host=get_localhost_ip()).pass_through()
        respx_mocker.get(
            "/",
            name="healthcheck",
        ).respond(status.HTTP_200_OK, json={"message": "ok"})
        respx_mocker.get("", name="base_endpoint").respond(status.HTTP_200_OK, json={})
        respx_mocker.get("/user/profile", name="get_user_profile").respond(
            status.HTTP_200_OK, json=faker.pydict(allowed_types=(str,))
        )
        list_datasets_re = re.compile(r"/datasets")
        respx_mocker.get(list_datasets_re, name="list_datasets").respond(
            status.HTTP_200_OK,
            json=Page.create(items=[], params=Params(size=10), total=0).model_dump(
                mode="json"
            ),
        )

        yield respx_mocker
