# pylint: disable=no-name-in-module
# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument


from collections.abc import Callable

import pytest
from aiopg.sa.exc import ResourceClosedError
from faker import Faker
from pytest_simcore.helpers.faker_factories import random_product
from simcore_postgres_database.webserver_models import products
from sqlalchemy.dialects.postgresql import insert as pg_insert


@pytest.fixture
def products_regex() -> dict:
    return {
        "s4l": r"(^s4l[\.-])|(^sim4life\.)",
        "osparc": r"^osparc.",
        "tis": r"(^ti.[\.-])|(^ti-solution\.)",
    }


@pytest.fixture
def products_names(products_regex: dict) -> list[str]:
    return list(products_regex)


@pytest.fixture
def make_products_table(products_regex: dict, faker: Faker) -> Callable:
    async def _make(conn) -> None:
        for n, (name, regex) in enumerate(products_regex.items()):

            result = await conn.execute(
                pg_insert(products)
                .values(
                    **random_product(
                        name=name,
                        display_name=f"Product {name.capitalize()}",
                        short_name=name[:3].lower(),
                        host_regex=regex,
                        priority=n,
                    )
                )
                .on_conflict_do_update(
                    index_elements=[products.c.name],
                    set_={
                        "display_name": f"Product {name.capitalize()}",
                        "short_name": name[:3].lower(),
                        "host_regex": regex,
                        "priority": n,
                    },
                )
            )

            assert result.closed
            assert not result.returns_rows
            with pytest.raises(ResourceClosedError):
                await result.scalar()

    return _make
