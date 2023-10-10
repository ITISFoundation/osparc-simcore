# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from typing import Any

import pytest
from pydantic import BaseModel
from servicelib.json_serialization import json_dumps
from simcore_service_webserver.products._db import Product


@pytest.mark.parametrize(
    "model_cls",
    [
        Product,
    ],
)
def test_product_examples(
    model_cls: type[BaseModel], model_cls_examples: dict[str, dict[str, Any]]
):
    for name, example in model_cls_examples.items():
        print(name, ":", json_dumps(example, indent=1))
        model_instance = model_cls(**example)
        assert model_instance, f"Failed with {name}"

        if isinstance(model_instance, Product):
            assert model_instance.to_statics()

            if "registration_email_template" in example:
                assert model_instance.get_template_name_for("registration_email.jinja2")


def test_product_to_static():

    product = Product.parse_obj(Product.Config.schema_extra["examples"][0])
    assert product.to_statics() == {
        "displayName": "o²S²PARC",
        "supportEmail": "support@osparc.io",
    }

    product = Product.parse_obj(Product.Config.schema_extra["examples"][2])

    assert product.to_statics() == {
        "displayName": "o²S²PARC FOO",
        "supportEmail": "foo@osparcf.io",
        "vendor": {
            "copyright": "© ACME correcaminos",
            "name": "ACME",
            "url": "https://acme.com",
            "license_url": "https://acme.com/license",
            "has_landing_page": False,
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
    }
