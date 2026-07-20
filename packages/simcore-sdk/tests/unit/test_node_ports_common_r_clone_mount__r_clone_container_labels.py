# pylint: disable=protected-access

from models_library.docker import DockerLabelKey
from pydantic import BaseModel, TypeAdapter
from simcore_sdk.node_ports_common.r_clone_mount._container import _RCloneContainerLabels


def _get_parseable_aliases(model: BaseModel) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for field_name, info in model.model_fields.items():
        va = info.validation_alias
        if va is None:
            va = info.alias or field_name
        if hasattr(va, "choices"):  # AliasChoices
            names = [c for c in va.choices if isinstance(c, str)]
        else:
            names = [va] if isinstance(va, str) else [field_name]
        result[field_name] = names
    return result


def test_r_clone_container_labels_validates_docker_label_keys():
    for property_name, aliases in _get_parseable_aliases(_RCloneContainerLabels).items():
        for alias in aliases:
            print(f"For {property_name=} Parsing {alias=}")
            assert TypeAdapter(DockerLabelKey).validate_python(alias)
