from collections.abc import Iterable
from dataclasses import dataclass
from typing import ClassVar

from ...generic_scheduler import Operation
from .._models import OperationType, SchedulerOperationName, SchedulingProfileType
from .._utils import get_scheduler_oepration_name
from . import legacy, new_style


@dataclass
class SchedulingProfile:
    start_name: SchedulerOperationName
    start_operation: Operation

    monitor_name: SchedulerOperationName
    monitor_operation: Operation

    stop_name: SchedulerOperationName
    stop_operation: Operation


class RegsteredSchedulingProfiles:
    _REGISTEERED_MODES: ClassVar[dict[SchedulingProfileType, SchedulingProfile]] = {}

    @classmethod
    def register(
        cls,
        scheduling_profile_type: SchedulingProfileType,
        *,
        start_operation: Operation,
        monitor_operation: Operation,
        stop_operation: Operation,
    ) -> None:
        cls._REGISTEERED_MODES[scheduling_profile_type] = SchedulingProfile(
            start_name=get_scheduler_oepration_name(
                OperationType.START,
                scheduling_profile_type,
            ),
            start_operation=start_operation,
            monitor_name=get_scheduler_oepration_name(
                OperationType.MONITOR,
                scheduling_profile_type,
            ),
            monitor_operation=monitor_operation,
            stop_name=get_scheduler_oepration_name(
                OperationType.STOP,
                scheduling_profile_type,
            ),
            stop_operation=stop_operation,
        )

    @classmethod
    def unregister(cls, scheduling_profile_type: SchedulingProfileType) -> None:
        cls._REGISTEERED_MODES.pop(scheduling_profile_type, None)

    @classmethod
    def get_profile(
        cls, scheduling_profile_type: SchedulingProfileType
    ) -> SchedulingProfile:
        return cls._REGISTEERED_MODES[scheduling_profile_type]

    @classmethod
    def iter_profiles(cls) -> Iterable[SchedulingProfile]:
        yield from cls._REGISTEERED_MODES.values()


def register_profiles() -> None:
    RegsteredSchedulingProfiles.register(
        SchedulingProfileType.LEGACY,
        start_operation=legacy.start.get_operation(),
        monitor_operation=legacy.monitor.get_operation(),
        stop_operation=legacy.stop.get_operation(),
    )
    RegsteredSchedulingProfiles.register(
        SchedulingProfileType.NEW_STYLE,
        start_operation=new_style.start.get_operation(),
        monitor_operation=new_style.monitor.get_operation(),
        stop_operation=new_style.stop.get_operation(),
    )


def unregister_profiles() -> None:
    RegsteredSchedulingProfiles.unregister(SchedulingProfileType.LEGACY)
    RegsteredSchedulingProfiles.unregister(SchedulingProfileType.NEW_STYLE)
