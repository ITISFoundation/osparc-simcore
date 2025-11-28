from collections.abc import Iterable
from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from ...generic_scheduler import Operation
from .._models import OperationType, SchedulerOperationName, SchedulingProfile
from .._utils import get_scheduler_oepration_name
from . import legacy, new_style


class SchedulingProfileData(BaseModel):
    start_name: SchedulerOperationName
    start_operation: Operation
    monitor_name: SchedulerOperationName
    monitor_operation: Operation
    stop_name: SchedulerOperationName
    stop_operation: Operation

    model_config = ConfigDict(arbitrary_types_allowed=True)


class RegsteredSchedulingProfiles:
    _REGISTEERED_MODES: ClassVar[dict[SchedulingProfile, SchedulingProfileData]] = {}

    @classmethod
    def add(
        cls,
        schedule_mode: SchedulingProfile,
        *,
        start_operation: Operation,
        monitor_operation: Operation,
        stop_operation: Operation,
    ) -> None:

        start_name = get_scheduler_oepration_name(OperationType.START, schedule_mode)
        monitor_name = get_scheduler_oepration_name(
            OperationType.MONITOR, schedule_mode
        )
        stop_name = get_scheduler_oepration_name(OperationType.STOP, schedule_mode)

        cls._REGISTEERED_MODES[schedule_mode] = SchedulingProfileData(
            start_name=start_name,
            start_operation=start_operation,
            monitor_name=monitor_name,
            monitor_operation=monitor_operation,
            stop_name=stop_name,
            stop_operation=stop_operation,
        )

    @classmethod
    def get_profile_data(
        cls, schedule_mode: SchedulingProfile
    ) -> SchedulingProfileData:
        return cls._REGISTEERED_MODES[schedule_mode]

    @classmethod
    def iter_profiles(cls) -> Iterable[SchedulingProfileData]:
        yield from cls._REGISTEERED_MODES.values()


# add all supported profiles here

RegsteredSchedulingProfiles.add(
    SchedulingProfile.LEGACY,
    start_operation=legacy.start.get_operation(),
    monitor_operation=legacy.monitor.get_operation(),
    stop_operation=legacy.stop.get_operation(),
)
RegsteredSchedulingProfiles.add(
    SchedulingProfile.NEW_STYLE,
    start_operation=new_style.start.get_operation(),
    monitor_operation=new_style.monitor.get_operation(),
    stop_operation=new_style.stop.get_operation(),
)
