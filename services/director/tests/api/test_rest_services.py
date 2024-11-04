# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import json
from urllib.parse import quote

import httpx
from fastapi import status
from fixtures.fake_services import ServiceInRegistryInfoDict
from helpers import json_schema_validator
from simcore_service_director import resources


def _assert_response_and_unwrap_envelope(got: httpx.Response):
    assert got.encoding == "application/json"

    body = got.json()
    assert isinstance(body, dict)
    assert "data" in body or "error" in body
    return body.get("data"), body.get("error")


def _assert_services(
    *,
    expected: list[ServiceInRegistryInfoDict],
    got: list[dict],
    schema_version="v1",
):
    assert len(expected) == len(got)

    expected_key_version_tuples = [
        (s["service_description"]["key"], s["service_description"]["version"])
        for s in expected
    ]

    json_schema_path = resources.get_path(resources.RESOURCE_NODE_SCHEMA)
    assert json_schema_path.exists() is True
    with json_schema_path.open() as file_pt:
        service_schema = json.load(file_pt)

    for service in got:
        service.pop("image_digest", None)
        if schema_version == "v1":
            assert (
                expected_key_version_tuples.count((service["key"], service["version"]))
                == 1
            )
        json_schema_validator.validate_instance_object(service, service_schema)


async def test_list_services_with_empty_registry(
    docker_registry: str,
    client: httpx.AsyncClient,
    api_version_prefix: str,
):
    assert docker_registry, "docker-registry is not ready?"

    # empty case
    resp = await client.get(f"/{api_version_prefix}/services")
    assert resp.status_code == status.HTTP_200_OK

    services, error = _assert_response_and_unwrap_envelope(resp.json())
    assert not error
    assert isinstance(services, list)

    _assert_services(expected=[], got=services)


async def test_list_services(
    docker_registry: str,
    client: httpx.AsyncClient,
    created_services: list[ServiceInRegistryInfoDict],
    api_version_prefix: str,
):
    assert docker_registry, "docker-registry is not ready?"

    resp = await client.get(f"/{api_version_prefix}/services")
    assert resp.status_code == status.HTTP_200_OK

    services, error = _assert_response_and_unwrap_envelope(resp.json())
    assert not error
    assert isinstance(services, list)

    _assert_services(expected=created_services, got=services)


async def test_get_service_bad_request(
    docker_registry: str,
    client: httpx.AsyncClient,
    created_services: list[ServiceInRegistryInfoDict],
    api_version_prefix: str,
):
    assert docker_registry, "docker-registry is not ready?"
    assert len(created_services) > 0

    resp = await client.get(f"/{api_version_prefix}/services?service_type=blahblah")
    assert resp.status_code == status.HTTP_400_BAD_REQUEST

    services, error = _assert_response_and_unwrap_envelope(resp.json())
    assert not services
    assert error


async def test_list_services_by_service_type(
    docker_registry: str,
    client: httpx.AsyncClient,
    created_services: list[ServiceInRegistryInfoDict],
    api_version_prefix: str,
):
    assert docker_registry, "docker-registry is not ready?"
    assert len(created_services) == 5

    resp = await client.get(
        f"/{api_version_prefix}/services?service_type=computational"
    )
    assert resp.status_code == status.HTTP_200_OK

    services, error = _assert_response_and_unwrap_envelope(resp.json())
    assert not error
    assert services
    assert len(services) == 3

    resp = await client.get(f"/{api_version_prefix}/services?service_type=interactive")
    assert resp.status_code == status.HTTP_200_OK

    services, error = _assert_response_and_unwrap_envelope(resp.json())
    assert not error
    assert services
    assert len(services) == 2


async def test_get_services_by_key_and_version_with_empty_registry(
    client: httpx.AsyncClient, api_version_prefix: str
):
    resp = await client.get(f"/{api_version_prefix}/services/whatever/someversion")
    assert resp.status_code == status.HTTP_400_BAD_REQUEST

    resp = await client.get(
        f"/{api_version_prefix}/services/simcore/services/dynamic/something/someversion"
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND

    resp = await client.get(
        f"/{api_version_prefix}/services/simcore/services/dynamic/something/1.5.2"
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


async def test_get_services_by_key_and_version(
    client: httpx.AsyncClient,
    created_services: list[ServiceInRegistryInfoDict],
    api_version_prefix: str,
):
    assert len(created_services) == 5

    retrieved_services: list[dict] = []
    for created_service in created_services:
        service_description = created_service["service_description"]
        # note that it is very important to remove the safe="/" from quote!!!!
        key, version = (
            quote(service_description[key], safe="") for key in ("key", "version")
        )
        url = f"/{api_version_prefix}/services/{key}/{version}"
        resp = await client.get(url)

        assert resp.status_code == status.HTTP_200_OK, f"Got f{resp.text}"

        services, error = _assert_response_and_unwrap_envelope(resp.json())
        assert not error
        assert isinstance(services, list)
        assert len(services) == 1

        retrieved_services.append(services[0])

    _assert_services(expected=created_services, got=retrieved_services)


async def test_get_service_labels(
    client: httpx.AsyncClient,
    created_services: list[ServiceInRegistryInfoDict],
    api_version_prefix: str,
):
    assert len(created_services) == 5

    for service in created_services:
        service_description = service["service_description"]
        # note that it is very important to remove the safe="/" from quote!!!!
        key, version = (
            quote(service_description[key], safe="") for key in ("key", "version")
        )
        url = f"/{api_version_prefix}/services/{key}/{version}/labels"
        resp = await client.get(url)
        assert resp.status_code == status.HTTP_200_OK, f"Got f{resp.text}"

        labels, error = _assert_response_and_unwrap_envelope(resp.json())
        assert not error

        assert service["docker_labels"] == labels


async def test_get_services_extras_by_key_and_version_with_empty_registry(
    client: httpx.AsyncClient, api_version_prefix: str
):
    resp = await client.get(
        f"/{api_version_prefix}/service_extras/whatever/someversion"
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    resp = await client.get(
        f"/{api_version_prefix}/service_extras/simcore/services/dynamic/something/someversion"
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    resp = await client.get(
        f"/{api_version_prefix}/service_extras/simcore/services/dynamic/something/1.5.2"
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


async def test_get_services_extras_by_key_and_version(
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

        service_extras, error = _assert_response_and_unwrap_envelope(resp.json())
        assert not error
        assert created_service["service_extras"] == service_extras
