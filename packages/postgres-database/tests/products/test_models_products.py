# pylint: disable=no-name-in-module
# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from collections.abc import Callable

import sqlalchemy as sa
from simcore_postgres_database.models.products import (
    EmailFeedback,
    Forum,
    IssueTracker,
    Manual,
    Vendor,
    WebFeedback,
)
from simcore_postgres_database.webserver_models import products
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncEngine


async def test_load_products(asyncpg_engine: AsyncEngine, make_products_table: Callable, products_regex: dict):
    exclude = {
        products.c.created,
        products.c.modified,
    }

    async with asyncpg_engine.connect() as conn:
        await make_products_table(conn)

        stmt = sa.select(*[c for c in products.columns if c not in exclude])
        result = await conn.execute(stmt)
        rows = result.fetchall()
        assert rows

        assert {row.name: row.host_regex for row in rows} == products_regex


async def test_insert_select_product(
    asyncpg_engine: AsyncEngine,
):
    osparc_product = {
        "name": "osparc",
        "display_name": "o²S²PARC",
        "short_name": "osparc",
        "host_regex": r"([\.-]{0,1}osparc[\.-])",
        "base_url": "https://osparc.io",
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
            Manual(label="main", url="doc.acme.com"),
            Manual(label="z43", url="yet-another-manual.acme.com"),
        ],
        "support": [
            Forum(label="forum", kind="forum", url="forum.acme.com"),
            EmailFeedback(label="email", kind="email", email="support@acme.com"),
            WebFeedback(label="web-form", kind="web", url="support.acme.com"),
        ],
    }

    async with asyncpg_engine.begin() as conn:
        # writes
        stmt = (
            pg_insert(products)
            .values(**osparc_product)
            .on_conflict_do_update(index_elements=[products.c.name], set_=osparc_product)
            .returning(products.c.name)
        )
        name = await conn.scalar(stmt)

        # reads
        stmt = sa.select(products).where(products.c.name == name)
        row = (await conn.execute(stmt)).one_or_none()
        assert row

        assert row.manuals
        assert row.manuals == osparc_product["manuals"]

        assert row.vendor == {
            "url": "https://acme.com",
            "name": "ACME",
            "copyright": "© ACME correcaminos",
        }
