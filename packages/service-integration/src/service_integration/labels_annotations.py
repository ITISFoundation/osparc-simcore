""" configuration is attached to user's docker image as label annotations

This module defines how config is serialized/deserialized to/from docker labels
"""

import json
from json.decoder import JSONDecodeError
from typing import Any

from pydantic.json import pydantic_encoder


def _json_dumps(obj: Any, **kwargs):
    return json.dumps(obj, default=pydantic_encoder, **kwargs)


def to_labels(
    config: dict[str, Any], *, prefix_key: str, trim_key_head: bool = True
) -> dict[str, str]:
    # FIXME: null is loaded as 'null' string value? is that correct? json -> None upon deserialization?
    labels = {}
    for key, value in config.items():
        if trim_key_head:
            if isinstance(value, str):
                # Avoids double quotes, i.e. '"${VERSION}"'
                label = value
            else:
                label = _json_dumps(value, sort_keys=False)
        else:
            label = _json_dumps({key: value}, sort_keys=False)

        # NOTE: docker-compose env var interpolation gets confused with schema's '$ref' and
        # will replace it '$ref' with an empty string.
        if isinstance(label, str) and "$ref" in label:
            label = label.replace("$ref", "$$ref")

        labels[f"{prefix_key}.{key}"] = label

    return labels


def from_labels(
    labels: dict[str, str], *, prefix_key: str, trim_key_head: bool = True
) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for key, label in labels.items():
        if key.startswith(f"{prefix_key}."):
            try:
                value = json.loads(label)
            except JSONDecodeError:
                value = label

            if not trim_key_head:
                if isinstance(value, dict):
                    data.update(value)
            else:
                data[key.replace(f"{prefix_key}.", "")] = value

    return data
