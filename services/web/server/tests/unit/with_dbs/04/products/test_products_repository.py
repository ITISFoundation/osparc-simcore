# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import contextlib
from typing import Any

import aiopg.sa
import pytest
import sqlalchemy as sa
from aiohttp import web
from aiohttp.test_utils import TestClient, make_mocked_request
from faker import Faker
from models_library.products import ProductName, ProductStripeInfoGet
from pytest_simcore.helpers.faker_factories import random_product
from pytest_simcore.helpers.postgres_tools import insert_and_get_row_lifespan
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
from simcore_postgres_database.utils_products_prices import ProductPriceInfo
from simcore_service_webserver.constants import (
    FRONTEND_APP_DEFAULT,
    FRONTEND_APPS_AVAILABLE,
)
from simcore_service_webserver.products._repository import ProductRepository
from simcore_service_webserver.products._web_middlewares import (
    _get_default_product_name,
)


@pytest.fixture(scope="module")
def products_raw_data(faker: Faker) -> dict[ProductName, dict[str, Any]]:
    default_product = random_product(fake=faker, name=FRONTEND_APP_DEFAULT)

    adminer_example = {
        # DATA introduced by operator e.g. in adminer
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
    }

    minimal_example = {
        "name": "s4llite",
        "display_name": "MINIMAL example",
        "short_name": "dummy",
        "host_regex": "([\\.-]{0,1}osparc[\\.-])",
        "support_email": "support@osparc.io",
    }

    examples = {}

    def _add(data):
        assert data["name"] not in examples
        assert data.get("group_id") is None  # note that group is not assigned
        examples.update({data["name"]: data})

    _add(adminer_example)
    _add(minimal_example)
    _add(default_product)

    for name in FRONTEND_APPS_AVAILABLE:
        if name not in examples:
            _add(random_product(fake=faker, name=name))

    return examples


@pytest.fixture(scope="module")
async def db_products_table_with_data(
    postgres_db: sa.engine.Engine, products_raw_data: dict[ProductName, dict[str, Any]]
):
    from sqlalchemy.ext.asyncio import create_async_engine

    asyncio_engine = create_async_engine(
        f"{postgres_db.url}".replace("postgresql", "postgresql+asyncpg")
    )
    try:
        async with contextlib.AsyncExitStack() as module_test_suite_fixture:
            product_to_row: dict[ProductName, dict[str, Any]] = {}

            for product_name, product_values in products_raw_data.items():
                product_row = await module_test_suite_fixture.enter_async_context(
                    insert_and_get_row_lifespan(
                        asyncio_engine,
                        table=products,
                        values=product_values,
                        pk_col=products.c.name,
                        pk_value=product_name,
                    )
                )
                product_to_row[product_name] = product_row

            yield product_to_row

            # will rm products

    finally:
        await asyncio_engine.dispose()


@pytest.fixture
def app(client: TestClient) -> web.Application:
    assert client.app
    return client.app


@pytest.fixture
async def product_repository(app: web.Application) -> ProductRepository:
    repo = ProductRepository.create_from_request(
        request=make_mocked_request("GET", "/fake", app=app)
    )
    assert repo.engine

    return repo


async def test_utils_products_and_webserver_default_product_in_sync(
    app: web.Application,
    product_repository: ProductRepository,
    aiopg_engine: aiopg.sa.engine.Engine,
):
    # tests definitions of default from utle_products and web-server.products are in sync
    async with aiopg_engine.acquire() as conn:
        default_product_name = await utils_products.get_default_product_name(conn)
        assert default_product_name == _get_default_product_name(app)

    default_product = await product_repository.get_product(default_product_name)
    assert default_product.name == default_product_name


async def test_product_repository_get_product(
    product_repository: ProductRepository,
):
    product_name = "tis"

    product = await product_repository.get_product(product_name)
    assert product
    assert product.name == product_name

    assert await product_repository.get_product("undefined") is None


async def test_product_repository_list_products_names(
    product_repository: ProductRepository,
):
    product_names = await product_repository.list_products_names()
    assert isinstance(product_names, list)
    assert all(isinstance(name, str) for name in product_names)


async def test_product_repository_get_product_latest_price_info_or_none(
    product_repository: ProductRepository,
):
    product_name = "tis"
    price_info = await product_repository.get_product_latest_price_info_or_none(
        product_name
    )
    assert price_info is None or isinstance(price_info, ProductPriceInfo)


async def test_product_repository_get_product_stripe_info(
    product_repository: ProductRepository,
):
    product_name = "tis"
    stripe_info = await product_repository.get_product_stripe_info(product_name)
    assert isinstance(stripe_info, ProductStripeInfoGet)


async def test_product_repository_get_template_content(
    product_repository: ProductRepository,
):
    template_name = "some_template"
    content = await product_repository.get_template_content(template_name)
    assert content is None or isinstance(content, str)


async def test_product_repository_get_product_template_content(
    product_repository: ProductRepository,
):
    product_name = "tis"
    content = await product_repository.get_product_template_content(product_name)
    assert content is None or isinstance(content, str)


async def test_product_repository_get_product_ui(product_repository: ProductRepository):
    product_name = "tis"
    ui = await product_repository.get_product_ui(product_name)
    assert ui is None or isinstance(ui, dict)
