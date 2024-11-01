# pylint: disable=redefined-outer-name

from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import arrow
import pytest
from faker import Faker
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    DynamicServiceStart,
)
from models_library.projects import ProjectID
from servicelib.deferred_tasks import TaskUID
from simcore_service_dynamic_scheduler.services.service_tracker._models import (
    SchedulerServiceState,
    TrackedServiceModel,
    UserRequestedState,
)


@pytest.mark.parametrize("requested_state", UserRequestedState)
@pytest.mark.parametrize("current_state", SchedulerServiceState)
@pytest.mark.parametrize("check_status_after", [1, arrow.utcnow().timestamp()])
@pytest.mark.parametrize("service_status_task_uid", [None, TaskUID("ok")])
def test_serialization(
    faker: Faker,
    requested_state: UserRequestedState,
    current_state: SchedulerServiceState,
    check_status_after: float,
    service_status_task_uid: TaskUID | None,
):
    tracked_model = TrackedServiceModel(
        dynamic_service_start=None,
        user_id=None,
        project_id=None,
        requested_state=requested_state,
        current_state=current_state,
        service_status=faker.pystr(),
        check_status_after=check_status_after,
        service_status_task_uid=service_status_task_uid,
    )

    as_bytes = tracked_model.to_bytes()
    assert as_bytes
    assert TrackedServiceModel.from_bytes(as_bytes) == tracked_model


@pytest.mark.parametrize(
    "dynamic_service_start",
    [
        None,
        DynamicServiceStart.parse_obj(
            DynamicServiceStart.Config.schema_extra["example"]
        ),
    ],
)
@pytest.mark.parametrize("project_id", [None, uuid4()])
async def test_set_check_status_after_to(
    dynamic_service_start: DynamicServiceStart | None, project_id: ProjectID | None
):
    model = TrackedServiceModel(
        dynamic_service_start=dynamic_service_start,
        user_id=None,
        project_id=project_id,
        requested_state=UserRequestedState.RUNNING,
    )
    assert model.check_status_after < arrow.utcnow().timestamp()

    delay = timedelta(seconds=4)

    before = (arrow.utcnow() + delay).timestamp()
    model.set_check_status_after_to(delay)
    after = (arrow.utcnow() + delay).timestamp()

    assert model.check_status_after
    assert before < model.check_status_after < after


async def test_legacy_format_compatibility(project_slug_dir: Path):
    legacy_format_path = (
        project_slug_dir / "tests" / "assets" / "legacy_tracked_service_model.bin"
    )
    assert legacy_format_path.exists()

    model_from_disk = TrackedServiceModel.from_bytes(legacy_format_path.read_bytes())

    model = TrackedServiceModel(
        dynamic_service_start=None,
        user_id=None,
        project_id=None,
        requested_state=UserRequestedState.RUNNING,
        # assume same dates are coming in
        check_status_after=model_from_disk.check_status_after,
        last_state_change=model_from_disk.last_state_change,
    )

    assert model_from_disk == model


def test_current_state_changes_updates_last_state_change():
    model = TrackedServiceModel(
        dynamic_service_start=None,
        user_id=None,
        project_id=None,
        requested_state=UserRequestedState.RUNNING,
    )

    last_changed = deepcopy(model.last_state_change)
    model.current_state = SchedulerServiceState.IDLE
    assert last_changed != model.last_state_change

    last_changed_2 = deepcopy(model.last_state_change)
    model.current_state = SchedulerServiceState.IDLE
    assert last_changed_2 == model.last_state_change

    assert last_changed != last_changed_2
