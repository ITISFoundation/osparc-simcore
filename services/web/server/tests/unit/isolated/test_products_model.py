# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import json
import re
from itertools import chain
from typing import Any

import pytest
import simcore_service_webserver.products
import sqlalchemy as sa
from faker import Faker
from models_library.products import ProductName
from pydantic import BaseModel
from pytest_simcore.helpers.faker_factories import random_product
from pytest_simcore.pydantic_models import (
    assert_validation_model,
    walk_model_examples_in_package,
)
from simcore_postgres_database.models.products import products as products_table
from simcore_service_webserver.constants import FRONTEND_APP_DEFAULT
from simcore_service_webserver.products._models import Product
from sqlalchemy import String
from sqlalchemy.dialects import postgresql


@pytest.mark.parametrize(
    "model_cls, example_name, example_data",
    chain(walk_model_examples_in_package(simcore_service_webserver.products)),
)
def test_all_products_models_examples(
    model_cls: type[BaseModel], example_name: str, example_data: Any
):
    model_instance = assert_validation_model(
        model_cls, example_name=example_name, example_data=example_data
    )

    # Some extra checks for Products
    if isinstance(model_instance, Product):
        assert model_instance.to_statics()
        if "registration_email_template" in example_data:
            assert model_instance.get_template_name_for("registration_email.jinja2")


def test_product_to_static():

    product = Product.model_validate(Product.model_json_schema()["examples"][0])
    assert product.to_statics() == {
        "displayName": "o²S²PARC",
        "supportEmail": "support@osparc.io",
    }

    product = Product.model_validate(Product.model_json_schema()["examples"][2])

    assert product.to_statics() == {
        "displayName": "o²S²PARC FOO",
        "supportEmail": "foo@osparcf.io",
        "vendor": {
            "copyright": "© ACME correcaminos",
            "name": "ACME",
            "url": "https://acme.com",
            "license_url": "https://acme.com/license",
            "invitation_form": True,
        },
        "issues": [
            {
                "label": "github",
                "login_url": "https://github.com/ITISFoundation/osparc-simcore",
                "new_url": "https://github.com/ITISFoundation/osparc-simcore/issues/new/choose",
            },
            {
                "label": "fogbugz",
                "login_url": "https://fogbugz.com/login",
                "new_url": "https://fogbugz.com/new?project=123",
            },
        ],
        "manuals": [
            {"label": "main", "url": "doc.acme.com"},
            {"label": "z43", "url": "yet-another-manual.acme.com"},
        ],
        "support": [
            {"kind": "forum", "label": "forum", "url": "forum.acme.com"},
            {"kind": "email", "label": "email", "email": "more-support@acme.com"},
            {"kind": "web", "label": "web-form", "url": "support.acme.com"},
        ],
        "isPaymentEnabled": False,
    }


def test_product_host_regex_with_spaces():
    data = Product.model_json_schema()["examples"][2]

    # with leading and trailing spaces and uppercase (tests anystr_strip_whitespace )
    data["support_email"] = "  fOO@BaR.COM    "

    # with leading trailing spaces (tests validator("host_regex", pre=True))
    expected = r"([\.-]{0,1}osparc[\.-])".strip()
    data["host_regex"] = expected + "   "

    # parsing should strip all whitespaces and normalize email
    product = Product.model_validate(data)

    assert product.host_regex.pattern == expected
    assert product.host_regex.search("osparc.bar.com")

    assert product.support_email == "foo@bar.com"


@pytest.fixture(scope="session")
def product_name() -> ProductName:
    return ProductName(FRONTEND_APP_DEFAULT)


def test_safe_load_empty_blanks_on_string_cols_from_db(
    faker: Faker, product_name: ProductName
):
    def _get_server_defaults():
        server_defaults = {}
        for c in products_table.columns:
            if c.server_default is not None:
                if isinstance(c.type, String):
                    server_defaults[c.name] = c.server_default.arg
                elif isinstance(c.type, postgresql.JSONB):
                    m = re.match(r"^'(.+)'::jsonb$", c.server_default.arg.text)
                    if m:
                        server_defaults[c.name] = json.loads(m.group(1))

        return server_defaults

    nullable_strings_column_names = [
        c.name
        for c in products_table.columns
        if isinstance(c.type, sa.String) and c.nullable
    ]

    server_defaults = _get_server_defaults()

    product_row_from_db = random_product(
        name=product_name,
        fake=faker,
        **{name: " " * len(name) for name in nullable_strings_column_names}
    )

    product = Product.model_validate(product_row_from_db)

    assert product.model_dump(include=set(nullable_strings_column_names)) == {
        name: None for name in nullable_strings_column_names
    }
