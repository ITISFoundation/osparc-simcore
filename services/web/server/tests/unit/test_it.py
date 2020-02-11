# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
import pytest
from aiohttp import web
from yarl import URL

from simcore_service_webserver.application import create_safe_application
from simcore_service_webserver.catalog import setup_catalog
from simcore_service_webserver.catalog_config import schema as catalog_schema


def test_it():
    front_url = URL("https://osparc.io/v0/catalog/dags/123?page_size=6")

    rel_url = front_url.relative()
    assert rel_url.path.startswith("/v0/catalog")

    new_path = rel_url.path.replace("/v0/catalog", "/v1")

    back_url = URL("http://catalog:8000").with_path(new_path).with_query(rel_url.query)

    assert str(back_url) == "http://catalog:8000/v1/dags/123?page_size=6"
