import urllib.parse
from typing import List, Tuple

# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access
import pytest
import respx
from fastapi import status


@pytest.fixture(autouse=True)
def minimal_director_config(monkeypatch):
    """set a minimal configuration for testing the director connection only"""
    monkeypatch.setenv("DIRECTOR_ENABLED", "1")
    monkeypatch.setenv("POSTGRES_ENABLED", "0")
    monkeypatch.setenv("CELERY_ENABLED", "0")
    monkeypatch.setenv("REGISTRY_ENABLED", "0")


@pytest.fixture
def mocked_director_v0_service_api(
    minimal_app, entrypoint, exp_status, exp_data, resp_alias
):
    with respx.mock(
        base_url=minimal_app.state.settings.director_v0.base_url(include_tag=False),
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:
        # lists services
        # the entrypoint must be non-encoded
        respx_mock.get(
            urllib.parse.unquote(entrypoint),
            content=exp_data,
            alias=resp_alias,
        )

        yield respx_mock


def _get_list_services_calls() -> List[Tuple]:
    return [
        (
            "/v0/services",
            status.HTTP_200_OK,
            {"data": ["service1", "service2"]},
            "list_all_services",
        ),
        (
            "/v0/services?service_type=computational",
            status.HTTP_200_OK,
            {"data": ["service1", "service2"]},
            "list_computational_services",
        ),
        (
            "/v0/services?service_type=dynamic",
            status.HTTP_200_OK,
            {"data": ["service1", "service2"]},
            "list_dynamic_services",
        ),
    ]


def _get_service_version_calls() -> List[Tuple]:
    # TODO: here we see the return value is currently not validated
    return [
        (
            "/v0/services/simcore%2Fservices%2Fdynamic%2Fmyservice/1.3.4",
            status.HTTP_200_OK,
            {"data": ["stuff about my service"]},
            "get_service_version",
        )
    ]


def _get_service_version_extras_calls() -> List[Tuple]:
    # TODO: here we see the return value is currently not validated
    return [
        (
            "/v0/services/simcore%2Fservices%2Fdynamic%2Fmyservice/1.3.4/extras",
            status.HTTP_200_OK,
            {"data": "extra stuff about my service"},
            "get_service_extras",
        )
    ]


@pytest.mark.parametrize(
    "entrypoint,exp_status,exp_data,resp_alias",
    _get_list_services_calls()
    + _get_service_version_calls()
    + _get_service_version_extras_calls(),
)
def test_forward_to_director(
    client, mocked_director_v0_service_api, entrypoint, exp_status, exp_data, resp_alias
):
    response = client.get(entrypoint)

    assert response.status_code == exp_status
    assert response.json() == exp_data
    assert mocked_director_v0_service_api[resp_alias].called
