from typing import Any, Dict, List, Type

import pytest
from pydantic import BaseModel

## PYDANTIC MODELS & SCHEMAS -----------------------------------------------------


@pytest.fixture
def model_cls_examples(model_cls: Type[BaseModel]) -> Dict[str, Dict[str, Any]]:
    """
    Extracts examples from pydantic model class Config
    """
    # Use by defining model_cls as test parametrization

    assert model_cls_examples, (
        f"Testing against a {model_cls} model that has NO examples. Add them in Config class. "
        "These are useful to test backwards compatibility and doc. "
        "SEE https://pydantic-docs.helpmanual.io/usage/schema/#schema-customization"
    )

    # checks exampleS setup in schema_extra
    examples_dict = model_cls.Config.schema_extra.get("examples", {})
    assert isinstance(examples_dict, dict), (
        "OpenAPI expects examples: {example-name: example-body, ...}. "
        "SEE https://swagger.io/docs/specification/adding-examples/"
    )

    # check example in schema_extra
    example = model_cls.Config.schema_extra.get("example")

    # collect all examples and creates fixture -> {example-name: example, ...}
    examples = {
        f"{model_cls.__name__}.example[{name}]": example
        for name, example in examples_dict.items()
    }
    if example:
        examples[f"{model_cls.__name__}.example"] = example

    return examples
