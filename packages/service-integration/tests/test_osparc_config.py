# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
from pathlib import Path
from pprint import pformat
from typing import Any

import pytest
import yaml
from models_library.service_settings_labels import SimcoreServiceSettingLabelEntry
from service_integration.osparc_config import (
    MetadataConfig,
    RuntimeConfig,
    SettingsItem,
)


@pytest.fixture
def labels(tests_data_dir: Path, labels_fixture_name: str) -> dict[str, str]:
    data = yaml.safe_load((tests_data_dir / "docker-compose-meta.yml").read_text())

    service_name = {
        "legacy": "dy-static-file-server",
        "service-sidecared": "dy-static-file-server-dynamic-sidecar",
        "compose-sidecared": "dy-static-file-server-dynamic-sidecar-compose-spec",
        "rocket": "rocket",
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
    "labels_fixture_name",
    ["legacy", "service-sidecared", "compose-sidecared", "rocket"],
)
def test_load_from_labels(
    labels: dict[str, str], labels_fixture_name: str, tmp_path: Path
):
    meta_cfg = MetadataConfig.from_labels_annotations(labels)
    runtime_cfg = RuntimeConfig.from_labels_annotations(labels)
    assert runtime_cfg.callbacks_mapping is not None

    print(meta_cfg.model_dump_json(exclude_unset=True, indent=2))
    print(runtime_cfg.model_dump_json(exclude_unset=True, indent=2))

    # create yamls from config
    for model in (runtime_cfg, meta_cfg):
        config_path = (
            tmp_path / f"{model.__class__.__name__.lower()}-{labels_fixture_name}.yml"
        )
        with open(config_path, "w") as fh:
            data = json.loads(
                model.model_dump_json(exclude_unset=True, by_alias=True, exclude_none=True)
            )
            yaml.safe_dump(data, fh, sort_keys=False)

        # reload from yaml and compare
        new_model = model.__class__.from_yaml(config_path)
        assert new_model == model


@pytest.mark.parametrize(
    "example_data",
    SimcoreServiceSettingLabelEntry.model_config["json_schema_extra"]["examples"],
)
def test_settings_item_in_sync_with_service_settings_label(
    example_data: dict[str, Any]
):
    print(pformat(example_data))

    # First we parse with SimcoreServiceSettingLabelEntry since it also supports backwards compatibility
    # and will upgrade old version
    example_model = SimcoreServiceSettingLabelEntry.model_validate(example_data)

    # SettingsItem is exclusively for NEW labels, so it should not support backwards compatibility
    new_model = SettingsItem(
        name=example_model.name,
        type=example_model.setting_type,
        value=example_model.value,
    )

    # check back
    SimcoreServiceSettingLabelEntry.model_validate(new_model.model_dump(by_alias=True))
