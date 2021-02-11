from typing import Any, Dict, List, Type

import pytest
from pydantic import BaseModel

## PYDANTIC MODELS & SCHEMAS -----------------------------------------------------


@pytest.fixture
def model_cls_examples(model_cls: Type[BaseModel]) -> List[Dict[str, Any]]:
    """
    Extracts examples from pydantic model class Config
    """
    # Use by defining model_cls as test parametrization
    # SEE https://pydantic-docs.helpmanual.io/usage/schema/#schema-customization
    examples = model_cls.Config.schema_extra.get("examples", [])
    example = model_cls.Config.schema_extra.get("example")
    if example:
        examples.append(example)

    assert model_cls_examples, (
        f"{model_cls} has NO examples. Add them in Config class."
        "These are useful to test backwards compatibility and doc."
    )

    return examples
