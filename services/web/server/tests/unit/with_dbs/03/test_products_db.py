# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from typing import Any

import pytest
import sqlalchemy as sa
from aiohttp import web
from aiohttp.test_utils import TestClient
from aiopg.sa.result import RowProxy
from pytest_mock import MockerFixture
from simcore_postgres_database.models.products import (
    EmailFeedback,
    Forum,
    IssueTracker,
    Manual,
    Vendor,
    WebFeedback,
    products,
)
from simcore_service_webserver.db import APP_DB_ENGINE_KEY
from simcore_service_webserver.products_db import ProductRepository


@pytest.fixture
def app(client: TestClient) -> web.Application:
    assert client.app
    return client.app


@pytest.fixture
async def product_row(app: web.Application, product_data: dict[str, Any]) -> RowProxy:
    """Injects product_data in products table and returns the associated table's database row

    Note that product_data is a SUBSET of product_row (e.g. modified dattimes etc)!
    """
    engine = app[APP_DB_ENGINE_KEY]
    assert engine

    async with engine.acquire() as conn:
        # writes
        stmt = products.insert().values(**product_data).returning(products.c.name)
        name = await conn.scalar(stmt)

        # reads
        stmt = sa.select(products).where(products.c.name == name)
        row = await (await conn.execute(stmt)).fetchone()
        assert row

        return row


@pytest.fixture
async def product_repository(
    app: web.Application, mocker: MockerFixture
) -> ProductRepository:
    assert product_row

    fake_request = mocker.MagicMock()
    fake_request.app = app

    repo = ProductRepository(request=fake_request)
    return repo


@pytest.mark.parametrize(
    "product_data",
    [
        # DATA introduced by operator e.g. in adminer
        {
            "name": "tis",
            "display_name": "1. COMPLETE example",
            "short_name": "dummy",
            "host_regex": r"([\.-]{0,1}dummy[\.-])",
            "support_email": "foo@osparc.io",
            "twilio_messaging_sid": None,
            "vendor": Vendor(
                name="ACME",
                copyright="© ACME correcaminos",
                url="https://acme.com",
            ),
            "issues": [
                IssueTracker(
                    label="github",
                    login_url="https://github.com/ITISFoundation/osparc-simcore",
                    new_url="https://github.com/ITISFoundation/osparc-simcore/issues/new/choose",
                ),
                IssueTracker(
                    label="fogbugz",
                    login_url="https://fogbugz.com/login",
                    new_url="https://fogbugz.com/new?project=123",
                ),
            ],
            "manuals": [
                Manual(label="main", manual_url="doc.acme.com"),
                Manual(label="z43", manual_url="yet-another-manual.acme.com"),
            ],
            "support": [
                Forum(label="forum", kind="forum", url="forum.acme.com"),
                EmailFeedback(label="email", kind="email", email="support@acme.com"),
                WebFeedback(label="web-form", kind="web", url="support.acme.com"),
            ],
        },
        # Minimal
        {
            "name": "dummy",
            "display_name": "2. MINIMAL example",
            "short_name": "dummy",
            "host_regex": "([\\.-]{0,1}osparc[\\.-])",
            "support_email": "support@osparc.io",
        },
    ],
    ids=lambda d: d["display_name"],
)
async def test_it(
    product_repository: ProductRepository,
    product_data: dict[str, Any],
    product_row: RowProxy,
):

    # check differences between the original product_data and the product_row in database
    assert set(product_data.keys()).issubset(set(product_row.keys()))

    common_keys = set(product_data.keys()).intersection(set(product_row.keys()))
    assert {k: product_data[k] for k in common_keys} == {
        k: product_row[k] for k in common_keys
    }

    assert product_repository.engine
