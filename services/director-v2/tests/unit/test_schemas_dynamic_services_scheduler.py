# pylint: disable=redefined-outer-name

from collections.abc import Iterator
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path

import pytest
from simcore_service_director_v2.models.dynamic_services_scheduler import SchedulerData


@pytest.fixture(
    scope="session",
    params=[
        "fake_scheduler_data.json",
        "fake_scheduler_data_compose_spec.json",
    ],
)
def fake_data_file_name(request):
    return request.param


@pytest.fixture
def fake_scheduler_data(mocks_dir: Path, fake_data_file_name: str) -> str:
    file = mocks_dir / fake_data_file_name
    assert file.exists()
    return file.read_text()


# UTILS


@contextmanager
def assert_copy_has_changes(original: SchedulerData) -> Iterator[SchedulerData]:
    to_change = deepcopy(original)

    yield to_change

    assert original != to_change


async def test_parse_saved_fake_scheduler_data(fake_scheduler_data: str) -> None:
    assert SchedulerData.model_validate_json(fake_scheduler_data)


def test_nested_compare(fake_scheduler_data: str) -> None:
    scheduler_data = SchedulerData.model_validate_json(fake_scheduler_data)

    with assert_copy_has_changes(scheduler_data) as to_change:
        to_change.paths_mapping.inputs_path = Path("/tmp")

    with assert_copy_has_changes(scheduler_data) as to_change:
        to_change.version = "2.0.5"

    with assert_copy_has_changes(scheduler_data) as to_change:
        to_change.port = 333333

    with assert_copy_has_changes(scheduler_data) as to_change:
        to_change.dynamic_sidecar.status.info = "some info"

    with assert_copy_has_changes(scheduler_data) as to_change:
        to_change.dynamic_sidecar.containers_inspect = []

    with assert_copy_has_changes(scheduler_data) as to_change:
        to_change.dynamic_sidecar.service_removal_state.was_removed = True
