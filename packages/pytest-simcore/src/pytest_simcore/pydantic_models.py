import copy
from typing import Any, Dict, Type

import pytest
from pydantic import BaseModel

## PYDANTIC MODELS & SCHEMAS -----------------------------------------------------


@pytest.fixture
def model_cls_examples(model_cls: Type[BaseModel]) -> Dict[str, Dict[str, Any]]:
    """
    Extracts examples from pydantic model class Config
    """

    # Use by defining model_cls as test parametrization
    assert model_cls, (
        f"Testing against a {model_cls} model that has NO examples. Add them in Config class. "
        "These are useful to test backwards compatibility and doc. "
        "SEE https://pydantic-docs.helpmanual.io/usage/schema/#schema-customization"
    )

    # checks exampleS setup in schema_extra
    examples_list = copy.deepcopy(model_cls.Config.schema_extra.get("examples", []))
    assert isinstance(examples_list, list), (
        "OpenAPI and json-schema differ regarding the format for exampleS."
        "The former is a dict and the latter an array. "
        "We follow json-schema here"
        "SEE https://json-schema.org/understanding-json-schema/reference/generic.html"
        "SEE https://swagger.io/docs/specification/adding-examples/"
    )

    # check example in schema_extra
    example = copy.deepcopy(model_cls.Config.schema_extra.get("example"))

    # collect all examples and creates fixture -> {example-name: example, ...}
    examples = {
        f"{model_cls.__name__}.example[{index}]": example
        for index, example in enumerate(examples_list)
    }
    if example:
        examples[f"{model_cls.__name__}.example"] = example

    return examples
