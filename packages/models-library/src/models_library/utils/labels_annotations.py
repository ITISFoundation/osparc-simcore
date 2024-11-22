""" Image labels annotations

osparc expects the service configuration (in short: config) attached to the service's image as label annotations.
This module defines how this config is serialized/deserialized to/from docker labels annotations
"""

import json
from json.decoder import JSONDecodeError
from typing import Any, TypeAlias

from common_library.json_serialization import json_dumps

LabelsAnnotationsDict: TypeAlias = dict[str, str]

# SEE https://docs.docker.com/config/labels-custom-metadata/#label-keys-and-values
#  "Authors of third-party tools should prefix each label key with the reverse DNS notation of a
#   domain they own, such as com.example.some-label ""
# FIXME: review and define a z43-wide inverse DNS e.g. swiss.z43
OSPARC_LABEL_PREFIXES = (
    "io.simcore",
    "simcore.service",
)


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
                label = json_dumps(value, sort_keys=False)
        else:
            label = json_dumps({key: value}, sort_keys=False)

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
