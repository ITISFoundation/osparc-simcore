import json
import pathlib
from pathlib import Path

import pydantic.json
import yaml
from models_library.service_settings_labels import (
    PathMappingsLabel,
    SimcoreServiceSettingLabelEntry,
    SimcoreServiceSettingsLabel,
)
from pydantic.main import BaseModel
from service_integration.osparc_image_spec import OsparcServiceSpecs
from service_integration.yaml_utils import yaml_safe_load

pydantic.json.ENCODERS_BY_TYPE[pathlib.PosixPath] = str


def test_it(tests_data_dir: Path):

    # consumes specs
    specs = yaml_safe_load((tests_data_dir / "metadata-dynamic.yml").read_text())

    with open(tests_data_dir / "service.yml") as fh:
        specs.update(yaml_safe_load(fh))

    service_specs = OsparcServiceSpecs.parse_obj(specs)

    labels = service_specs.to_labels_annotations()

    print(json.dumps(labels, indent=2))
    assert labels["simcore.service.paths-mapping"] == str(
        {
            "inputs_path": "/config/workspace/inputs",
            "outputs_path": "/config/workspace/outputs",
            "state_paths": ["/config"],
        }
    )

    assert OsparcServiceSpecs.from_labels_annotations(labels) == service_specs
