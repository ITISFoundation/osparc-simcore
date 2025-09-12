# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument


import asyncio
from collections.abc import AsyncIterable, Awaitable, Callable
from contextlib import AsyncExitStack
from copy import deepcopy
from secrets import choice
from typing import Final

import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from pydantic import NonNegativeInt
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.utils import limited_gather
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
from simcore_service_dynamic_scheduler.core.application import create_app
from simcore_service_dynamic_scheduler.services.generic_scheduler._core import (
    Operation,
    get_core,
)
from simcore_service_dynamic_scheduler.services.generic_scheduler._models import (
    ScheduleId,
)
from simcore_service_dynamic_scheduler.services.generic_scheduler._operation import (
    BaseStep,
    OperationRegistry,
    ParallelStepGroup,
    SingleStepGroup,
)
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_delay,
    wait_fixed,
)

pytest_simcore_core_services_selection = [
    "rabbit",
    "redis",
]
pytest_simcore_ops_services_selection = [
    "redis-commander",
]

_PARALLEL_APP_CREATION: Final[NonNegativeInt] = 5


@pytest.fixture
def disable_other_generic_scheduler_modules(mocker: MockerFixture) -> None:
    # these also use redis
    generic_scheduler_module = (
        "simcore_service_dynamic_scheduler.services.generic_scheduler"
    )
    mocker.patch(f"{generic_scheduler_module}._store.lifespan")
    mocker.patch(f"{generic_scheduler_module}._core.lifespan")


@pytest.fixture
def app_environment(
    disable_postgres_lifespan: None,
    disable_service_tracker_lifespan: None,
    disable_notifier_lifespan: None,
    disable_status_monitor_lifespan: None,
    app_environment: EnvVarsDict,
    rabbit_service: RabbitSettings,
    redis_service: RedisSettings,
    remove_redis_data: None,
) -> EnvVarsDict:
    return app_environment


@pytest.fixture
async def get_app(
    app_environment: EnvVarsDict,
) -> AsyncIterable[Callable[[], Awaitable[FastAPI]]]:
    exit_stack = AsyncExitStack()

    started_apps: list[FastAPI] = []

    async def _() -> FastAPI:
        app = create_app()
        started_apps.append(app)

        await exit_stack.enter_async_context(LifespanManager(app))
        return app

    yield _

    await exit_stack.aclose()


@pytest.fixture
async def selected_app(
    get_app: Callable[[], Awaitable[FastAPI]], app_count: NonNegativeInt
) -> FastAPI:
    # initialize a bunch of apps and randomly select one
    # this will make sure that there is competition events catching possible issues
    apps: list[FastAPI] = await limited_gather(
        *[get_app() for _ in range(app_count)], limit=_PARALLEL_APP_CREATION
    )
    return choice(apps)


_STEPS_CALL_ORDER: list[tuple[str, str]] = []

_CREATED: Final[str] = "create"
_REVERTED: Final[str] = "revert"


class _BS(BaseStep):
    @classmethod
    async def create(cls, app: FastAPI) -> None:
        _ = app
        _STEPS_CALL_ORDER.append((cls.__name__, _CREATED))

    @classmethod
    async def revert(cls, app: FastAPI) -> None:
        _ = app
        _STEPS_CALL_ORDER.append((cls.__name__, _REVERTED))


class _BaseExpectedStepOrder:
    def __init__(self, *steps: type[BaseStep]) -> None:
        self.steps = steps


class _CreateSequence(_BaseExpectedStepOrder):
    """steps appear in a sequence as CREATE"""


class _CreateRandom(_BaseExpectedStepOrder):
    """steps appear in any given order as CREATE"""


class _RevertSequence(_BaseExpectedStepOrder):
    """steps appear in a sequence as REVERT"""


class _RevertRandom(_BaseExpectedStepOrder):
    """steps appear in any given order as REVERT"""


def _asseert_order(*expected: _BaseExpectedStepOrder) -> None:
    call_order = deepcopy(_STEPS_CALL_ORDER)

    def _check_sequence(
        tracked: list[tuple[str, str]],
        steps: tuple[type[BaseStep], ...],
        *,
        expected_status: str,
    ) -> None:
        for step in steps:
            step_name, actual = tracked.pop(0)
            assert step_name == step.__name__
            assert actual == expected_status

    def _check_random(
        tracked: list[tuple[str, str]],
        steps: tuple[type[BaseStep], ...],
        *,
        expected_status: str,
    ) -> None:
        names = [step.__name__ for step in steps]
        for _ in steps:
            step_name, actual = tracked.pop(0)
            assert step_name in names
            assert actual == expected_status
            names.remove(step_name)

    for group in expected:
        if isinstance(group, _CreateSequence):
            _check_sequence(call_order, group.steps, expected_status=_CREATED)
        elif isinstance(group, _CreateRandom):
            _check_random(call_order, group.steps, expected_status=_CREATED)
        elif isinstance(group, _RevertSequence):
            _check_sequence(call_order, group.steps, expected_status=_REVERTED)
        elif isinstance(group, _RevertRandom):
            _check_random(call_order, group.steps, expected_status=_REVERTED)
        else:
            msg = f"Unknown {group=}"
            raise NotImplementedError(msg)
    assert not call_order, f"Left overs {call_order=}"


class _PeelPotates(_BS): ...


class _BoilPotates(_BS): ...


class _MashPotates(_BS): ...


class _AddButter(_BS): ...


class _AddSalt(_BS): ...


class _AddPepper(_BS): ...


class _AddPaprika(_BS): ...


class _AddMint(_BS): ...


class _AddMilk(_BS): ...


class _StirTillDone(_BS): ...


_MASHED_POTATOES: Final[Operation] = [
    SingleStepGroup(_PeelPotates),
    SingleStepGroup(_BoilPotates),
    SingleStepGroup(_MashPotates),
    ParallelStepGroup(
        _AddButter, _AddSalt, _AddPepper, _AddPaprika, _AddMint, _AddMilk
    ),
    SingleStepGroup(_StirTillDone),
]

OperationRegistry.register("mash_potatoes", _MASHED_POTATOES)  # type: ignore[call-arg


@pytest.mark.parametrize(
    "app_count",
    [
        1,
        # 10, # TODO: figure out why it's not working with more than one app in parall
    ],
)
async def test_core_workflow(
    preserve_caplog_for_async_logging: None, selected_app: FastAPI
):
    schedule_id: ScheduleId = await get_core(selected_app).create("mash_potatoes", {})
    print(f"started {schedule_id=}")

    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(5),
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            await asyncio.sleep(0)  # wait for envet to trigger
            assert len(_STEPS_CALL_ORDER) == 10
            _asseert_order(
                _CreateSequence(
                    _PeelPotates,
                    _BoilPotates,
                    _MashPotates,
                ),
                _CreateRandom(
                    _AddButter, _AddSalt, _AddPepper, _AddPaprika, _AddMint, _AddMilk
                ),
                _CreateSequence(_StirTillDone),
            )


# TODO: also add a test with 2 of the cores in parallel to see it still works as expected
