# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
import json
from pathlib import Path
from typing import Dict, Iterator, Optional

import pytest

import yaml


@pytest.fixture
def port_type() -> str:
    return ""


@pytest.fixture
def label_cfg(metadata_file: Path, port_type: str) -> Dict:
    ports_type = f"{port_type}s"
    with metadata_file.open() as fp:
        cfg = yaml.safe_load(fp)
        assert ports_type in cfg
        return cfg[ports_type]


@pytest.fixture
def validation_folder(validation_dir: Path, port_type: str) -> Path:
    return validation_dir / port_type


@pytest.fixture
def validation_cfg(validation_dir: Path, port_type: str) -> Optional[Dict]:
    validation_file = validation_dir / \
        port_type / (f"{port_type}s.json")
    if validation_file.exists():
        with validation_file.open() as fp:
            return json.load(fp)
    # it may not exist if only files are required
    return None


def _find_key_in_cfg(filename: str, value: Dict) -> Iterator[str]:
    for k, v in value.items():
        if k == filename:
            if isinstance(v, dict):
                assert "data:" in v["type"]
                yield k
            else:
                yield v
        elif isinstance(v, dict):
            for result in _find_key_in_cfg(filename, v):
                yield result


@pytest.mark.parametrize("port_type", [
    "input",
    "output"
])
def test_validation_data_follows_definition(label_cfg: Dict, validation_cfg: Dict, validation_folder: Path):
    for key, value in label_cfg.items():
        assert "type" in value

        # rationale: files are on their own and other types are in inputs.json
        if not "data:" in value["type"]:
            # check that keys are available
            assert key in validation_cfg, f"missing {key} in validation config file"
        else:
            # it's a file and it should be in the folder as well using key as the filename
            filename_to_look_for = key
            if "fileToKeyMap" in value:
                # ...or there is a mapping
                assert len(value["fileToKeyMap"]) > 0
                for filename, mapped_value in value["fileToKeyMap"].items():
                    assert mapped_value == key, f"file to key map for {key} has an incorrectly set {mapped_value}, it should be equal to {key}"
                    filename_to_look_for = filename
                    assert (validation_folder / filename_to_look_for).exists(
                    ), f"{filename_to_look_for} is missing from {validation_folder}"
            else:
                assert (validation_folder / filename_to_look_for).exists(
                ), f"{filename_to_look_for} is missing from {validation_folder}"

    if validation_cfg:
        for key, value in validation_cfg.items():
            # check the key is defined in the labels
            assert key in label_cfg
            label2types = {
                "number": (float, int),
                "integer": int,
                "boolean": bool,
                "string": str
            }
            if not "data:" in label_cfg[key]["type"]:
                # check the type is correct
                assert isinstance(value, label2types[label_cfg[key]["type"]]
                                  ), f"{value} has not the expected type {label2types[label_cfg[key]['type']]}"

    for path in validation_folder.glob("**/*"):
        if path.name in ["inputs.json", "outputs.json", ".gitkeep"]:
            continue
        assert path.is_file(), f"{path} is not a file!"
        filename = path.name
        # this filename shall be available as a key in the labels somewhere
        key = next(_find_key_in_cfg(str(filename), label_cfg))

        assert key in label_cfg, f"{key} was not found in {label_cfg}"
