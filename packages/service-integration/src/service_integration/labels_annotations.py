import json
from typing import Any, Dict

from pydantic.json import pydantic_encoder


def json_dumps(obj: Any, **kwargs):
    return json.dumps(obj, default=pydantic_encoder, **kwargs)


def to_labels(
    data: Dict, *, prefix_key: str = "io.simcore", trim_key_head: bool = True
) -> Dict[str, str]:
    # TODO: connect this with models
    # FIXME: null is loaded as 'null' string value? is that correct? json -> None upon deserialization?
    labels = {}
    for key, value in data.items():
        if trim_key_head:
            if isinstance(value, str):
                # TODO: Q&D for ${} variables
                label = value
            else:
                label = json_dumps(value, sort_keys=False)
        else:
            label = json_dumps({key: value}, sort_keys=False)

        labels[f"{prefix_key}.{key}"] = label

    return labels
