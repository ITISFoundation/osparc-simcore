# pylint:disable = redefined-outer-name

from pathlib import Path

import pytest
from common_library.json_serialization import json_dumps, json_loads
from pydantic import TypeAdapter
from simcore_service_director_v2.models.dynamic_services_scheduler import SchedulerData


@pytest.fixture
def legacy_scheduler_data_format(mocks_dir: Path) -> Path:
    fake_service_path = mocks_dir / "legacy_scheduler_data_format.json"
    assert fake_service_path.exists()
    return fake_service_path


def test_regression_as_label_data(scheduler_data: SchedulerData) -> None:
    # golden reference format: the model's JSON payload with `compose_spec` kept as
    # a JSON-encoded string (see PR #3610); the old implementation obtained it by
    # assigning the string into the `Json[...]` field, which pydantic serialized
    # with a warning — here the payload is built directly instead
    legacy_payload = scheduler_data.model_dump(mode="json")
    legacy_payload["compose_spec"] = json_dumps(legacy_payload["compose_spec"])
    json_encoded = json_dumps(legacy_payload)

    # using pydantic's internals
    label_data = scheduler_data.as_label_data()

    # the label must keep `compose_spec` double-encoded (string within JSON)
    assert json_loads(json_loads(label_data)["compose_spec"]) == scheduler_data.compose_spec

    parsed_json_encoded = SchedulerData.model_validate_json(json_encoded)
    parsed_label_data = SchedulerData.model_validate_json(label_data)
    assert parsed_json_encoded == parsed_label_data


def test_ensure_legacy_format_compatibility(legacy_scheduler_data_format: Path):
    # Ensure no further PRs can break this format

    # PRs applying changes to the legacy format:
    # - https://github.com/ITISFoundation/osparc-simcore/pull/3610
    assert TypeAdapter(list[SchedulerData]).validate_json(legacy_scheduler_data_format.read_text())
