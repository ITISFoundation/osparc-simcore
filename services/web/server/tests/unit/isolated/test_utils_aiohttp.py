# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import json
from typing import Any
from unittest.mock import Mock, patch
from uuid import UUID

import pytest
from aiohttp import web
from faker import Faker
from pydantic import BaseModel
from simcore_service_webserver.utils_aiohttp import (
    envelope_json_response,
    get_api_base_url,
    iter_origins,
)


@pytest.fixture
def data(faker: Faker) -> dict[str, Any]:
    class Point(BaseModel):
        x: int
        y: int
        uuid: UUID

    return {
        "str": faker.word(),
        "float": faker.pyfloat(),
        "int": faker.pyint(),
        "object-pydantic": Point(x=faker.pyint(), y=faker.pyint(), uuid=faker.uuid4()),
        "object": {"name": faker.name(), "surname": faker.name()},
    }


@pytest.fixture
def make_request():
    def _make_request(headers=None, scheme="http", host="example.com"):
        req = Mock(spec=web.Request)
        req.headers = headers or {}
        req.scheme = scheme
        req.host = host
        return req

    return _make_request


def test_enveloped_successful_response(data: dict):
    resp = envelope_json_response(data, web.HTTPCreated)
    assert resp.text is not None

    resp_body = json.loads(resp.text)
    assert {"data"} == set(resp_body.keys())


def test_enveloped_failing_response():

    resp = envelope_json_response(
        {"message": "could not find it", "reason": "invalid id"}, web.HTTPNotFound
    )
    assert resp.text is not None

    assert {"error"} == set(json.loads(resp.text).keys())


@pytest.mark.parametrize(
    "headers, expected_output",
    [
        # No headers - fallback to request
        (
            {},
            [("http", "localhost")],
        ),
        # Single entry
        (
            {"X-Forwarded-Proto": "https", "X-Forwarded-Host": "example.com"},
            [("https", "example.com"), ("http", "localhost")],
        ),
        # Multiple entries with ports
        (
            {
                "X-Forwarded-Proto": "https, http",
                "X-Forwarded-Host": "api.example.com:443, 192.168.1.1:8080",
            },
            [
                ("https", "api.example.com"),
                ("http", "192.168.1.1"),
                ("http", "localhost"),
            ],
        ),
        # Unequal list lengths (proto longer)
        (
            {
                "X-Forwarded-Proto": "http, https, ftp",
                "X-Forwarded-Host": "site.com, cdn.site.com",
            },
            [("http", "site.com"), ("https", "cdn.site.com"), ("http", "localhost")],
        ),
        # With whitespace
        (
            {
                "X-Forwarded-Proto": "  https ,  http ",
                "X-Forwarded-Host": "  example.com  ,  proxy.com ",
            },
            [("https", "example.com"), ("http", "proxy.com"), ("http", "localhost")],
        ),
        # Duplicate entries
        (
            {
                "X-Forwarded-Proto": "https, https",
                "X-Forwarded-Host": "example.com, example.com",
            },
            [("https", "example.com"), ("http", "localhost")],
        ),
    ],
)
def test_iter_origins(headers, expected_output):
    request = Mock(
        spec=web.Request,
        headers=headers,
        scheme="http",
        host="localhost:8080",  # Port should be stripped
    )

    results = list(iter_origins(request))

    assert results == expected_output


def test_no_forwarded_headers_regular_host(make_request):
    req = make_request()
    with patch("common_library.network.is_ip_address", return_value=False):
        url = get_api_base_url(req)
    assert url == "http://api.example.com"


def test_no_forwarded_headers_ip_host(make_request):
    req = make_request(host="192.168.1.2")
    with patch("common_library.network.is_ip_address", return_value=True):
        url = get_api_base_url(req)
    assert url == "http://192.168.1.2"


def test_with_forwarded_headers(make_request):
    headers = {"X-Forwarded-Proto": "https", "X-Forwarded-Host": "mydomain.com"}
    req = make_request(headers=headers, scheme="http", host="example.com")
    with patch("common_library.network.is_ip_address", return_value=False):
        url = get_api_base_url(req)
    assert url == "https://api.mydomain.com"


def test_with_multiple_forwarded_headers(make_request):
    headers = {
        "X-Forwarded-Proto": "https, http",
        "X-Forwarded-Host": "api1.com, api2.com",
    }
    req = make_request(headers=headers, scheme="http", host="example.com")
    with patch("common_library.network.is_ip_address", side_effect=[False, False]):
        url = get_api_base_url(req)
    assert url == "https://api.api1.com"


def test_forwarded_host_with_port(make_request):
    headers = {"X-Forwarded-Proto": "https", "X-Forwarded-Host": "mydomain.com:8080"}
    req = make_request(headers=headers, scheme="http", host="example.com:8080")
    with patch("common_library.network.is_ip_address", return_value=False):
        url = get_api_base_url(req)
    assert url == "https://api.mydomain.com"


def test_empty_forwarded_headers_fallback(make_request):
    headers = {"X-Forwarded-Proto": "", "X-Forwarded-Host": ""}
    req = make_request(headers=headers, scheme="https", host="example.com")
    with patch("common_library.network.is_ip_address", return_value=False):
        url = get_api_base_url(req)
    assert url == "https://api.example.com"
