from typing import Any, Dict, List, Type

from pydantic import BaseModel


def extract_examples(model_cls: Type[BaseModel]) -> List[Dict[str, Any]]:
    """ Extracts examples from pydantic classes"""

    examples = []

    schema_extra = model_cls.__config__.schema_extra
    if schema_extra and isinstance(schema_extra, dict):
        examples = schema_extra.get("examples", [])
        if example := schema_extra.get("example"):
            examples.append(example)

    # TODO: extract as well from the fields?

    return examples
