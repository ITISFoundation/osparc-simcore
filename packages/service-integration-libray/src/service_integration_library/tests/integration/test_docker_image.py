# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json
import shutil
import urllib.request
from pathlib import Path
from typing import Dict

import pytest

import docker
import jsonschema
import yaml


# HELPERS
def _download_url(url: str, file: Path):
    # Download the file from `url` and save it locally under `file_name`:
    with urllib.request.urlopen(url) as response, file.open('wb') as out_file:
        shutil.copyfileobj(response, out_file)
    assert file.exists()


def _convert_to_simcore_labels(image_labels: Dict) -> Dict:
    io_simcore_labels = {}
    for key, value in image_labels.items():
        if str(key).startswith("io.simcore."):
            simcore_label = json.loads(value)
            simcore_keys = list(simcore_label.keys())
            assert len(simcore_keys) == 1
            simcore_key = simcore_keys[0]
            simcore_value = simcore_label[simcore_key]
            io_simcore_labels[simcore_key] = simcore_value
    assert len(io_simcore_labels) > 0
    return io_simcore_labels

# FIXTURES
@pytest.fixture
def osparc_service_labels_jsonschema(tmp_path) -> Dict:
    url = "https://raw.githubusercontent.com/ITISFoundation/osparc-simcore/master/api/specs/common/schemas/node-meta-v0.0.1.json"
    file_name = tmp_path / "service_label.json"
    _download_url(url, file_name)
    with file_name.open() as fp:
        json_schema = json.load(fp)
        return json_schema


@pytest.fixture(scope='session')
def metadata_labels(metadata_file: Path) -> Dict:
    with metadata_file.open() as fp:
        metadata = yaml.safe_load(fp)
        return metadata

# TESTS


def test_docker_io_simcore_labels_against_files(docker_image: docker.models.images.Image, metadata_labels: Dict):
    image_labels = docker_image.labels
    io_simcore_labels = _convert_to_simcore_labels(image_labels)
    # check files are identical
    for key, value in io_simcore_labels.items():
        assert key in metadata_labels
        assert value == metadata_labels[key]


def test_validate_docker_io_simcore_labels(docker_image: docker.models.images.Image, osparc_service_labels_jsonschema: Dict):
    image_labels = docker_image.labels
    # get io labels
    io_simcore_labels = _convert_to_simcore_labels(image_labels)
    # validate schema
    try:
        jsonschema.validate(io_simcore_labels,
                            osparc_service_labels_jsonschema)
    except jsonschema.SchemaError:
        pytest.fail("Schema {} contains errors".format(
            osparc_service_labels_jsonschema))
    except jsonschema.ValidationError:
        pytest.fail("Failed to validate docker image io labels against schema")
