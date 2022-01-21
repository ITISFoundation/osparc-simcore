from typing import Any, Dict, List, Type, Union

from pydantic import BaseModel
from pydantic.config import SchemaExtraCallable


def extract_examples(model_cls: Type[BaseModel]) -> List[Dict[str, Any]]:
    """Extracts examples from pydantic classes"""

    examples = []

    schema_extra: Union[
        Dict[str, Any], SchemaExtraCallable
    ] = model_cls.__config__.schema_extra

    if isinstance(schema_extra, dict):
        # NOTE: Sometimes an example (singular) mistaken
        # by exampleS. The assertions below should
        # help catching this error while running tests

        examples = schema_extra.get("examples", [])
        assert isinstance(examples, list)  # nosec

        if example := schema_extra.get("example"):
            assert not isinstance(example, list)  # nosec
            examples.append(example)

    # TODO: treat SchemaExtraCallable case (so far we only have one example)
    # TODO: extract examples from single fields and compose model?

    return examples
