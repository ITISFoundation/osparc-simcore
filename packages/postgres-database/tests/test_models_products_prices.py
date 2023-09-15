# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import random
from typing import Any

import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from pytest_simcore.helpers.rawdata_fakers import FAKE, random_user
from simcore_postgres_database.models.products import products
from simcore_postgres_database.models.products_prices import products_prices
from simcore_postgres_database.models.users import users


def random_product(
    group_id: int | None = None,
    registration_email_template: str | None = None,
    **overrides
) -> dict[str, Any]:
    data = {
        "name": FAKE.unique.word(),
        "display_name": FAKE.word(),
        "short_name": FAKE.word()[:11],
        "host_regex": FAKE.regexify(r"[a-zA-Z0-9]+\.com"),
        "support_email": FAKE.email(),
        "twilio_messaging_sid": FAKE.uuid4(),
        "vendor": {
            "key1": FAKE.word(),
            "key2": FAKE.word(),
        },
        "issues": [{"issue_key": FAKE.word()}],
        "manuals": [{"title": FAKE.sentence()}],
        "support": [{"type": "Forum"}],
        "login_settings": {
            "setting1": FAKE.word(),
            "setting2": FAKE.word(),
        },
        "registration_email_template": registration_email_template,
        "max_open_studies_per_user": random.randint(1, 10),  # noqa: S311
        "group_id": group_id,
    }
    assert set(data.keys()).issubset({c.name for c in products.columns})

    data.update(overrides)

    return data


async def test_creating_product_prices(connection: SAConnection):
    # a user
    result = await connection.execute(
        users.insert()
        .values(random_user(primary_gid=1))
        .returning(sa.literal_column("*"))
    )
    user = await result.first()
    assert user

    # a product
    result = await connection.execute(
        products.insert()
        .values(random_product(group_id=None))
        .returning(sa.literal_column("*"))
    )
    product = await result.first()
    assert product

    # a price per product
    result = await connection.execute(
        products_prices.insert()
        .values(
            product_name=product.name,
            dollars_per_credit=100,
            authorized_by=user.id,
        )
        .returning(sa.literal_column("*"))
    )
    product_prices = await result.first()
    assert product_prices

    # check if the user is PO when the price is setup
