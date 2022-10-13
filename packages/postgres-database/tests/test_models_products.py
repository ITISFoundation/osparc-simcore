# pylint: disable=no-name-in-module
# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument


from pathlib import Path
from typing import Callable

import pytest
import sqlalchemy as sa
from aiopg.sa.engine import Engine
from aiopg.sa.exc import ResourceClosedError
from aiopg.sa.result import ResultProxy, RowProxy
from simcore_postgres_database.models.jinja2_templates import jinja2_templates
from simcore_postgres_database.webserver_models import products


@pytest.fixture
def product_sample() -> dict:
    return {
        "osparc": r"^osparc.",
        "s4l": r"(^s4l[\.-])|(^sim4life\.)",
        "tis": r"(^ti.[\.-])|(^ti-solution\.)",
    }


@pytest.fixture
def make_products_table(
    product_sample: dict,
) -> Callable:
    async def _make(conn) -> None:
        for name, regex in product_sample.items():
            result = await conn.execute(
                products.insert().values(name=name, host_regex=regex)
            )

            assert result.closed
            assert not result.returns_rows
            with pytest.raises(ResourceClosedError):
                await result.scalar()

    return _make


async def test_load_products(
    pg_engine: Engine, make_products_table: Callable, product_sample: dict
):
    exclude = {
        products.c.created,
        products.c.modified,
    }

    async with pg_engine.acquire() as conn:
        await make_products_table(conn)

        stmt = sa.select([c for c in products.columns if c not in exclude])
        result: ResultProxy = await conn.execute(stmt)
        assert result.returns_rows

        rows: list[RowProxy] = await result.fetchall()
        assert rows

        assert {
            row[products.c.name]: row[products.c.host_regex] for row in rows
        } == product_sample


async def test_jinja2_templates_table(
    pg_engine: Engine, osparc_simcore_services_dir: Path
):

    templates_common_dir = (
        osparc_simcore_services_dir
        / "web/server/src/simcore_service_webserver/templates/common"
    )

    async with pg_engine.acquire() as conn:

        templates = []
        # templates table
        for p in templates_common_dir.glob("*.jinja2"):
            name = await conn.scalar(
                jinja2_templates.insert()
                .values(name=p.name, content=p.read_text())
                .returning(jinja2_templates.c.name)
            )
            templates.append(name)

        # choose one
        registration_email_template = next(n for n in templates if "registration" in n)

        # products table
        for params in [
            {
                "name": "osparc",
                "host_regex": r"^osparc.",
                "registration_email_template": registration_email_template,
            },
            {
                "name": "s4l",
                "host_regex": r"(^s4l[\.-])|(^sim4life\.)",
                "short_name": "s4l web",
                "registration_email_template": registration_email_template,
            },
            {
                "name": "tis",
                "short_name": "TIP",
                "host_regex": r"(^ti.[\.-])|(^ti-solution\.)",
            },
        ]:
            #  aiopg doesn't support executemany!!
            await conn.execute(
                products.insert().values(**params),
            )

        # prints those products having customized templates
        j = products.join(jinja2_templates)
        stmt = sa.select(
            [products.c.name, jinja2_templates.c.name, products.c.short_name]
        ).select_from(j)

        result: ResultProxy = await conn.execute(stmt)
        assert result.rowcount == 2
        assert await result.fetchall() == [
            ("s4l", "registration_email.jinja2", "s4l web"),
            ("osparc", "registration_email.jinja2", "osparc"),
        ]

        assert (
            await conn.scalar(
                sa.select([jinja2_templates.c.content])
                .select_from(j)
                .where(products.c.name == "s4l")
            )
            is not None
        )

        assert (
            await conn.scalar(
                sa.select([jinja2_templates.c.content])
                .select_from(j)
                .where(products.c.name == "tis")
            )
            is None
        )
