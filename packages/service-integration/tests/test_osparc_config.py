# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
from pathlib import Path
from pprint import pformat
from typing import Any, Type

import pytest
import yaml
from models_library.service_settings_labels import SimcoreServiceSettingLabelEntry
from pydantic import BaseModel
from service_integration.osparc_config import MetaConfig, RuntimeConfig, SettingsItem


@pytest.fixture
def labels(tests_data_dir: Path, labels_fixture_name: str) -> dict[str, str]:
    data = yaml.safe_load((tests_data_dir / "docker-compose-meta.yml").read_text())

    service_name = {
        "legacy": "dy-static-file-server",
        "service-sidecared": "dy-static-file-server-dynamic-sidecar",
        "compose-sidecared": "dy-static-file-server-dynamic-sidecar-compose-spec",
    }

    labels_annotations = data["services"][service_name[labels_fixture_name]]["build"][
        "labels"
    ]

    # patch -> replaces some environs
    if compose_spec := labels_annotations.get("simcore.service.compose-spec"):
        if compose_spec == "${DOCKER_COMPOSE_SPECIFICATION}":
            labels_annotations["simcore.service.compose-spec"] = json.dumps(
                yaml.safe_load((tests_data_dir / "compose-spec.yml").read_text())
            )
    return labels_annotations


@pytest.mark.parametrize(
    "labels_fixture_name", ["legacy", "service-sidecared", "compose-sidecared"]
)
def test_load_from_labels(
    labels: dict[str, str], labels_fixture_name: str, tmp_path: Path
):
    meta_cfg = MetaConfig.from_labels_annotations(labels)
    runtime_cfg = RuntimeConfig.from_labels_annotations(labels)

    print(meta_cfg.json(exclude_unset=True, indent=2))
    print(runtime_cfg.json(exclude_unset=True, indent=2))

    # create yamls from config
    for model in (runtime_cfg, meta_cfg):
        config_path = (
            tmp_path / f"{model.__class__.__name__.lower()}-{labels_fixture_name}.yml"
        )
        with open(config_path, "wt") as fh:
            data = json.loads(
                model.json(exclude_unset=True, by_alias=True, exclude_none=True)
            )
            yaml.safe_dump(data, fh, sort_keys=False)

        # reload from yaml and compare
        new_model = model.__class__.from_yaml(config_path)
        assert new_model == model


@pytest.mark.parametrize(
    "model_cls",
    (SimcoreServiceSettingLabelEntry,),
)
def test_settings_item_in_sync_with_service_settings_label(
    model_cls: Type[BaseModel], model_cls_examples: dict[str, dict[str, Any]]
):
    for name, example in model_cls_examples.items():
        print(name, ":", pformat(example))
        SettingsItem.parse_obj(**example)
