# pylint: disable=no-name-in-module
# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument


import shutil
from collections.abc import Callable
from pathlib import Path

import pytest
import sqlalchemy as sa
from faker import Faker
from simcore_postgres_database.models.jinja2_templates import jinja2_templates
from simcore_postgres_database.models.products import products
from simcore_postgres_database.models.products_to_templates import products_to_templates
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture
def templates_names(faker: Faker) -> list[str]:
    return [faker.file_name(extension="html") for _ in range(3)]


@pytest.fixture
def templates_dir(
    tmp_path: Path, products_names: list[str], templates_names: list[str]
) -> Path:
    templates_path = tmp_path / "templates"

    # common keeps default templates
    (templates_path / "common").mkdir(parents=True)
    for template_name in templates_names:
        (templates_path / "common" / template_name).write_text(
            "Fake template for 'common'"
        )

    # only odd products have the first template
    for product_name in products_names[1::2]:
        (templates_path / product_name).mkdir(parents=True)
        (templates_path / product_name / templates_names[0]).write_text(
            f"Fake template for {product_name=}"
        )

    return templates_path


@pytest.fixture
async def product_templates_in_db(
    asyncpg_engine: AsyncEngine,
    make_products_table: Callable,
    products_names: list[str],
    templates_names: list[str],
):
    async with asyncpg_engine.begin() as conn:
        await make_products_table(conn)

        # one version of all tempaltes
        for template_name in templates_names:
            await conn.execute(
                jinja2_templates.insert().values(
                    name=template_name, content="fake template in database"
                )
            )

            # only even products have templates
            for product_name in products_names[0::2]:
                await conn.execute(
                    products_to_templates.insert().values(
                        template_name=template_name, product_name=product_name
                    )
                )


async def test_export_and_import_table(
    asyncpg_engine: AsyncEngine,
    product_templates_in_db: None,
):

    async with asyncpg_engine.connect() as connection:
        exported_values = []
        excluded_names = {"created", "modified", "group_id"}
        result = await connection.stream(
            sa.select(*(c for c in products.c if c.name not in excluded_names))
        )
        async for row in result:
            assert row
            exported_values.append(row._asdict())

        # now just upsert them
        for values in exported_values:
            values["display_name"] += "-changed"
            await connection.execute(
                pg_insert(products)
                .values(**values)
                .on_conflict_do_update(index_elements=[products.c.name], set_=values)
            )


async def test_create_templates_products_folder(
    asyncpg_engine: AsyncEngine,
    templates_dir: Path,
    products_names: list[str],
    tmp_path: Path,
    templates_names: list[str],
    product_templates_in_db: None,
):
    download_path = tmp_path / "downloaded" / "templates"
    assert templates_dir != download_path

    for product_name in products_names:
        product_folder = download_path / product_name
        product_folder.mkdir(parents=True, exist_ok=True)

        # takes common as defaults
        for p in (templates_dir / "common").iterdir():
            if p.is_file():
                shutil.copy(p, product_folder / p.name, follow_symlinks=False)

        # overrides with customs in-place
        if (templates_dir / product_name).exists():
            for p in (templates_dir / product_name).iterdir():
                if p.is_file():
                    shutil.copy(p, product_folder / p.name, follow_symlinks=False)

        # overrides if with files in database
        async with asyncpg_engine.connect() as conn:
            result = await conn.stream(
                sa.select(
                    products_to_templates.c.product_name,
                    jinja2_templates.c.name,
                    jinja2_templates.c.content,
                )
                .select_from(products_to_templates.join(jinja2_templates))
                .where(products_to_templates.c.product_name == product_name)
            )

            async for row in result:
                assert row
                template_path = product_folder / row.name
                template_path.write_text(row.content)

            assert sorted(
                product_folder / template_name for template_name in templates_names
            ) == sorted(product_folder.rglob("*.*"))
