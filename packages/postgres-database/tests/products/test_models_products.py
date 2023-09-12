# pylint: disable=no-name-in-module
# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument


import json
from collections.abc import Callable
from pathlib import Path
from pprint import pprint

import sqlalchemy as sa
from aiopg.sa.engine import Engine
from aiopg.sa.result import ResultProxy, RowProxy
from simcore_postgres_database.models.jinja2_templates import jinja2_templates
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


async def test_load_products(
    pg_engine: Engine, make_products_table: Callable, products_regex: dict
):
    exclude = {
        products.c.created,
        products.c.modified,
    }

    async with pg_engine.acquire() as conn:
        await make_products_table(conn)

        stmt = sa.select(*[c for c in products.columns if c not in exclude])
        result: ResultProxy = await conn.execute(stmt)
        assert result.returns_rows

        rows: list[RowProxy] = await result.fetchall()
        assert rows

        assert {
            row[products.c.name]: row[products.c.host_regex] for row in rows
        } == products_regex


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
                pg_insert(products)
                .values(**params)
                .on_conflict_do_update(
                    index_elements=[products.c.name],
                    set_=params,
                ),
            )

        # prints those products having customized templates
        j = products.join(jinja2_templates)
        stmt = sa.select(
            products.c.name, jinja2_templates.c.name, products.c.short_name
        ).select_from(j)

        result: ResultProxy = await conn.execute(stmt)
        assert result.rowcount == 2
        rows = await result.fetchall()
        assert sorted(r.as_tuple() for r in rows) == sorted(
            [
                ("osparc", "registration_email.jinja2", "osparc"),
                ("s4l", "registration_email.jinja2", "s4l web"),
            ]
        )

        assert (
            await conn.scalar(
                sa.select(jinja2_templates.c.content)
                .select_from(j)
                .where(products.c.name == "s4l")
            )
            is not None
        )

        assert (
            await conn.scalar(
                sa.select(jinja2_templates.c.content)
                .select_from(j)
                .where(products.c.name == "tis")
            )
            is None
        )


async def test_insert_select_product(
    pg_engine: Engine,
):
    osparc_product = {
        "name": "osparc",
        "display_name": "o²S²PARC",
        "short_name": "osparc",
        "host_regex": r"([\.-]{0,1}osparc[\.-])",
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

    print(json.dumps(osparc_product))

    async with pg_engine.acquire() as conn:
        # writes
        stmt = (
            pg_insert(products)
            .values(**osparc_product)
            .on_conflict_do_update(
                index_elements=[products.c.name], set_=osparc_product
            )
            .returning(products.c.name)
        )
        name = await conn.scalar(stmt)

        # reads
        stmt = sa.select(products).where(products.c.name == name)
        row = await (await conn.execute(stmt)).fetchone()
        print(row)
        assert row

        pprint(dict(**row))

        assert row.manuals
        assert row.manuals == osparc_product["manuals"]

        assert row.vendor == {
            "url": "https://acme.com",
            "name": "ACME",
            "copyright": "© ACME correcaminos",
        }
