# pylint: disable=redefined-outer-name

from copy import deepcopy
from pathlib import Path
from attr import attr
import pytest
from typing import Any, Callable, Any
import json
from simcore_service_director_v2.models.schemas.dynamic_services.scheduler import (
    SchedulerData,
)
from dataclasses import dataclass


@dataclass
class Change:
    target_prop: Callable[[SchedulerData], Any]
    attr_name: str
    value: Any


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


async def test_parse_saved_fake_scheduler_data(fake_scheduler_data: str) -> None:
    assert SchedulerData.parse_obj(json.loads(fake_scheduler_data))


@pytest.mark.parametrize(
    "change",
    [
        Change(
            target_prop=lambda x: x.paths_mapping,
            attr_name="inputs_path",
            value=Path("/tmp"),
        ),
        Change(target_prop=lambda x: x, attr_name="version", value="2.0.5"),
        Change(target_prop=lambda x: x.dynamic_sidecar, attr_name="port", value=33333),
        Change(
            target_prop=lambda x: x.dynamic_sidecar.status,
            attr_name="info",
            value="some info",
        ),
        Change(
            target_prop=lambda x: x.dynamic_sidecar,
            attr_name="containers_inspect",
            value=[],
        ),
        Change(
            target_prop=lambda x: x.dynamic_sidecar.service_removal_state,
            attr_name="was_removed",
            value=True,
        ),
    ],
)
async def test_nested_compare(fake_scheduler_data: str, change: Change) -> None:
    scheduler_data = SchedulerData.parse_obj(json.loads(fake_scheduler_data))
    original_scheduler_data = deepcopy(scheduler_data)

    # apply change
    change.target_prop(scheduler_data).__setattr__(change.attr_name, change.value)

    assert original_scheduler_data != scheduler_data
