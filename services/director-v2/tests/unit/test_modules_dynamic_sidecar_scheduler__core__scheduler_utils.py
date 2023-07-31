# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import pytest
from pytest import LogCaptureFixture
from simcore_service_director_v2.models.dynamic_services_scheduler import (
    DynamicSidecarStatus,
    SchedulerData,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._core._scheduler_utils import (
    LOG_MSG_MANUAL_INTERVENTION,
    service_awaits_manual_interventions,
)


@pytest.fixture
def scheduler_data_manual_intervention(scheduler_data: SchedulerData) -> SchedulerData:
    scheduler_data.dynamic_sidecar.status.current = DynamicSidecarStatus.FAILING
    scheduler_data.dynamic_sidecar.wait_for_manual_intervention_after_error = True
    return scheduler_data


async def test_service_awaits_manual_interventions_logs_once(
    caplog: LogCaptureFixture, scheduler_data_manual_intervention: SchedulerData
):
    caplog.clear()

    for _ in range(10):
        await service_awaits_manual_interventions(scheduler_data_manual_intervention)

    # message is only logged once
    assert caplog.text.count(LOG_MSG_MANUAL_INTERVENTION) == 1
