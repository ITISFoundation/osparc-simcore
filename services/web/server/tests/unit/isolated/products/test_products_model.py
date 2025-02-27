# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import re
from typing import Any

import pytest
import simcore_service_webserver.products
import sqlalchemy as sa
from faker import Faker
from models_library.basic_regex import TWILIO_ALPHANUMERIC_SENDER_ID_RE
from models_library.products import ProductName
from pydantic import BaseModel, ValidationError
from pytest_simcore.helpers.faker_factories import random_product
from pytest_simcore.pydantic_models import (
    assert_validation_model,
    walk_model_examples_in_package,
)
from simcore_postgres_database.models.products import products as products_table
from simcore_service_webserver.products.models import Product


@pytest.mark.parametrize(
    "model_cls, example_name, example_data",
    walk_model_examples_in_package(simcore_service_webserver.products),
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


def test_safe_load_empty_blanks_on_string_cols_from_db(
    fake_product_from_db: dict[str, Any]
):
    nullable_strings_column_names = [
        c.name
        for c in products_table.columns
        if isinstance(c.type, sa.String) and c.nullable
    ]

    fake_product_from_db.update(
        {name: " " * len(name) for name in nullable_strings_column_names}
    )

    product = Product.model_validate(fake_product_from_db)

    assert product.model_dump(include=set(nullable_strings_column_names)) == {
        name: None for name in nullable_strings_column_names
    }


@pytest.mark.parametrize(
    "expected_product_name",
    [
        "osparc",
        "s4l",
        "s4lacad",
        "s4ldesktop",
        "s4ldesktopacad",
        "s4lengine",
        "s4llite",
        "tiplite",
        "tis",
    ],
)
def test_product_name_needs_front_end(
    faker: Faker,
    expected_product_name: ProductName,
    product_db_server_defaults: dict[str, Any],
):
    product_from_db = random_product(
        name=expected_product_name,
        fake=faker,
        **product_db_server_defaults,
    )
    product = Product.model_validate(product_from_db)
    assert product.name == expected_product_name


def test_product_name_invalid(fake_product_from_db: dict[str, Any]):
    # Test with an invalid name
    fake_product_from_db.update(name="invalid name")
    with pytest.raises(ValidationError):
        Product.model_validate(fake_product_from_db)


def test_twilio_sender_id_is_truncated(fake_product_from_db: dict[str, Any]):
    fake_product_from_db.update(short_name=None, display_name="very long name" * 12)
    product = Product.model_validate(fake_product_from_db)

    assert re.match(
        TWILIO_ALPHANUMERIC_SENDER_ID_RE, product.twilio_alpha_numeric_sender_id
    )


def test_template_names_from_file(fake_product_from_db: dict[str, Any]):
    fake_product_from_db.update(registration_email_template="some_template_name_id")
    product = Product.model_validate(fake_product_from_db)

    assert (
        product.get_template_name_for(filename="registration_email.jinja2")
        == "some_template_name_id"
    )
    assert product.get_template_name_for(filename="other_template.jinja2") is None

    fake_product_from_db.update(registration_email_template=None)
    product = Product.model_validate(fake_product_from_db)
    assert (
        product.get_template_name_for(filename="registration_email_template.jinja2")
        is None
    )
