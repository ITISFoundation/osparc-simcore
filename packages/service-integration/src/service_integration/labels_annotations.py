""" Image labels annotations

osparc expects the service configuration (in short: config) attached to the service's image as label annotations.
This module defines how this config is serialized/deserialized to/from docker labels annotations
"""

import json
from json.decoder import JSONDecodeError
from typing import Any

from pydantic.json import pydantic_encoder

LabelsAnnotationsDict = dict[str, str]


def _json_dumps(obj: Any, **kwargs) -> str:
    return json.dumps(obj, default=pydantic_encoder, **kwargs)


def to_labels(
    config: dict[str, Any], *, prefix_key: str, trim_key_head: bool = True
) -> LabelsAnnotationsDict:
    """converts config into labels annotations"""

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
    labels: LabelsAnnotationsDict, *, prefix_key: str, trim_key_head: bool = True
) -> dict[str, Any]:
    """convert labels annotations into config"""
    config: dict[str, Any] = {}
    for key, label in labels.items():
        if key.startswith(f"{prefix_key}."):
            try:
                value = json.loads(label)
            except JSONDecodeError:
                value = label

            if not trim_key_head:
                if isinstance(value, dict):
                    config.update(value)
            else:
                config[key.replace(f"{prefix_key}.", "")] = value

    return config
