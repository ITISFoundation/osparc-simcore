# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from urllib.parse import quote

import httpx
from fastapi import status
from fixtures.fake_services import ServiceInRegistryInfoDict
from pytest_simcore.helpers.typing_env import EnvVarsDict


def _assert_response_and_unwrap_envelope(got: httpx.Response):
    assert got.headers["content-type"] == "application/json"
    assert got.encoding == "utf-8"

    body = got.json()
    assert isinstance(body, dict)
    assert "data" in body or "error" in body
    return body.get("data"), body.get("error")


async def test_get_services_extras_by_key_and_version_with_empty_registry(
    configure_registry_access: EnvVarsDict,
    client: httpx.AsyncClient,
    api_version_prefix: str,
):
    resp = await client.get(
        f"/{api_version_prefix}/service_extras/whatever/someversion"
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, f"Got f{resp.text}"
    resp = await client.get(
        f"/{api_version_prefix}/service_extras/simcore/services/dynamic/something/someversion"
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, f"Got f{resp.text}"
    resp = await client.get(
        f"/{api_version_prefix}/service_extras/simcore/services/dynamic/something/1.5.2"
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND, f"Got f{resp.text}"


async def test_get_services_extras_by_key_and_version(
    configure_registry_access: EnvVarsDict,
    client: httpx.AsyncClient,
    created_services: list[ServiceInRegistryInfoDict],
    api_version_prefix: str,
):
    assert len(created_services) == 5

    for created_service in created_services:
        service_description = created_service["service_description"]
        # note that it is very important to remove the safe="/" from quote!!!!
        key, version = (
            quote(service_description[key], safe="") for key in ("key", "version")
        )
        url = f"/{api_version_prefix}/service_extras/{key}/{version}"
        resp = await client.get(url)

        assert resp.status_code == status.HTTP_200_OK, f"Got {resp.text=}"

        service_extras, error = _assert_response_and_unwrap_envelope(resp)
        assert not error
        assert created_service["service_extras"] == service_extras
