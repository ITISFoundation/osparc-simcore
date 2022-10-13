# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from typing import Any

import pytest
from pydantic import BaseModel
from servicelib.json_serialization import json_dumps
from simcore_service_webserver.products_db import Product


@pytest.mark.parametrize(
    "model_cls",
    (Product,),
)
def test_product_examples(
    model_cls: type[BaseModel], model_cls_examples: dict[str, dict[str, Any]]
):
    for name, example in model_cls_examples.items():
        print(name, ":", json_dumps(example, indent=1))
        model_instance = model_cls(**example)
        assert model_instance, f"Failed with {name}"

        if isinstance(model_cls, Product):
            assert model_instance.to_statics()

            if "registration_email_template" in example:
                assert model_instance.get_template_name_for("registration_email.jinja2")
