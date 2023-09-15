# pylint:disable = redefined-outer-name

import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import parse_file_as
from simcore_service_director_v2.models.dynamic_services_scheduler import SchedulerData


@pytest.fixture
def legacy_scheduler_data_format(mocks_dir: Path) -> Path:
    fake_service_path = mocks_dir / "legacy_scheduler_data_format.json"
    assert fake_service_path.exists()
    return fake_service_path


@pytest.mark.testit  # MATUS: this needs to run!
def test_regression_as_label_data(scheduler_data: SchedulerData) -> None:
    # old tested implementation
    scheduler_data_copy = deepcopy(scheduler_data)
    scheduler_data_copy.compose_spec = json.dumps(scheduler_data_copy.compose_spec)
    json_encoded = scheduler_data_copy.json()

    # using pydantic's internals
    label_data = scheduler_data.as_label_data()

    parsed_json_encoded = SchedulerData.parse_raw(json_encoded)
    parsed_label_data = SchedulerData.parse_raw(label_data)
    assert parsed_json_encoded == parsed_label_data


@pytest.mark.testit  # MATUS: this needs to run!
def test_ensure_legacy_format_compatibility(legacy_scheduler_data_format: Path):
    # Ensure no further PRs can break this format

    # PRs applying changes to the legacy format:
    # - https://github.com/ITISFoundation/osparc-simcore/pull/3610
    assert parse_file_as(list[SchedulerData], legacy_scheduler_data_format)
