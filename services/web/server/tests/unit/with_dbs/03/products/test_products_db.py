# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Any

import pytest
import sqlalchemy as sa
from aiohttp import web
from aiohttp.test_utils import TestClient
from aiopg.sa.result import RowProxy
from pytest_mock import MockerFixture
from simcore_postgres_database import utils_products
from simcore_postgres_database.models.products import (
    EmailFeedback,
    Forum,
    IssueTracker,
    Manual,
    Vendor,
    WebFeedback,
    products,
)
from simcore_service_webserver.db.plugin import APP_AIOPG_ENGINE_KEY
from simcore_service_webserver.products._db import ProductRepository
from simcore_service_webserver.products._middlewares import _get_default_product_name
from simcore_service_webserver.products._model import Product


@pytest.fixture
def app(client: TestClient) -> web.Application:
    assert client.app
    return client.app


@pytest.fixture
async def product_row(app: web.Application, product_data: dict[str, Any]) -> RowProxy:
    """Injects product_data in products table and returns the associated table's database row

    Note that product_data is a SUBSET of product_row (e.g. modified dattimes etc)!
    """
    engine = app[APP_AIOPG_ENGINE_KEY]
    assert engine

    async with engine.acquire() as conn:
        # writes
        insert_stmt = (
            products.insert().values(**product_data).returning(products.c.name)
        )
        name = await conn.scalar(insert_stmt)

        # reads
        select_stmt = sa.select(products).where(products.c.name == name)
        row = await (await conn.execute(select_stmt)).fetchone()
        assert row

        return row


@pytest.fixture
async def product_repository(
    app: web.Application, mocker: MockerFixture
) -> ProductRepository:
    assert product_row

    fake_request = mocker.MagicMock()
    fake_request.app = app

    return ProductRepository.create_from_request(request=fake_request)


@pytest.mark.parametrize(
    "product_data",
    [
        # DATA introduced by operator e.g. in adminer
        {
            "name": "tis",
            "display_name": "COMPLETE example",
            "short_name": "dummy",
            "host_regex": r"([\.-]{0,1}dummy[\.-])",
            "support_email": "foo@osparc.io",
            "twilio_messaging_sid": None,
            "vendor": Vendor(
                name="ACME",
                copyright="© ACME correcaminos",
                url="https://acme.com",
                license_url="http://docs.acme.app/#/license-terms",
                invitation_url="http://docs.acme.app/#/how-to-request-invitation",
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
                Manual(label="main", url="doc.acme.com"),
                Manual(label="z43", url="yet-another-manual.acme.com"),
            ],
            "support": [
                Forum(label="forum", kind="forum", url="forum.acme.com"),
                EmailFeedback(label="email", kind="email", email="support@acme.com"),
                WebFeedback(label="web-form", kind="web", url="support.acme.com"),
            ],
        },
        # Minimal
        {
            "name": "s4llite",
            "display_name": "MINIMAL example",
            "short_name": "dummy",
            "host_regex": "([\\.-]{0,1}osparc[\\.-])",
            "support_email": "support@osparc.io",
        },
    ],
    ids=lambda d: d["display_name"],
)
async def test_product_repository_get_product(
    product_repository: ProductRepository,
    product_data: dict[str, Any],
    product_row: RowProxy,
    app: web.Application,
    mocker: MockerFixture,
):

    # check differences between the original product_data and the product_row in database
    assert set(product_data.keys()).issubset(set(product_row.keys()))

    common_keys = set(product_data.keys()).intersection(set(product_row.keys()))
    assert {k: product_data[k] for k in common_keys} == {
        k: product_row[k] for k in common_keys
    }

    # check RowProxy -> pydantic's Product
    product = Product.from_orm(product_row)

    print(product.json(indent=1))

    # product repo
    assert product_repository.engine

    assert await product_repository.get_product(product.name) == product

    # tests definitions of default from utle_products and web-server.products are in sync
    async with product_repository.engine.acquire() as conn:
        default_product = await utils_products.get_default_product_name(conn)
        assert default_product == _get_default_product_name(app)
