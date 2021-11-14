# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from pathlib import Path
from pprint import pprint
from typing import Any, Dict

import pytest
import yaml
from service_integration.labels_annotations import from_labels, to_labels


@pytest.fixture
def metadata_config(tests_data_dir: Path):
    config = yaml.safe_load((tests_data_dir / "metadata.yml").read_text())
    # adds some env-vars
    # FIXME: if version is set as '1.0' then pydantic will resolve it as a float!!
    config.update({"schema-version": "1.0.0", "build-date": "${BUILD_DATE}"})
    return config


@pytest.mark.parametrize("trim_key_head", (True, False))
def test_to_and_from_labels(metadata_config: Dict[str, Any], trim_key_head: bool):

    metadata_labels = to_labels(
        metadata_config, prefix_key="swiss.itisfoundation", trim_key_head=trim_key_head
    )
    pprint(metadata_labels)

    assert all(key.startswith("swiss.itisfoundation.") for key in metadata_labels)

    got_config = from_labels(
        metadata_labels, prefix_key="swiss.itisfoundation", trim_key_head=trim_key_head
    )
    assert got_config == metadata_config
