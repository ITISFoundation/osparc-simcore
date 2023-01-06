# pylint: disable=protected-access
# pylint: disable=redefined-outer-name

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any

import pytest
from fastapi import FastAPI
from pytest import LogCaptureFixture
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._context_base import (
    ContextIOInterface,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._errors import (
    PlayNotFoundException,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._marker import (
    mark_action,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._models import (
    ActionName,
    SceneName,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._play_context import (
    PlayContext,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._player import (
    ExceptionInfo,
    PlayerManager,
    _iter_index_action,
    scene_player,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._scene import (
    PlayCatalog,
    Scene,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _player_manager_lifecycle(player_manager: PlayerManager) -> None:
    try:
        await player_manager.start()
        yield None
    finally:
        await player_manager.shutdown()


async def test_iter_index_action():
    async def first():
        pass

    async def second():
        pass

    async def third():
        pass

    awaitables = [first, second, third]
    action_sequence = list(enumerate(awaitables))

    three_element_list = list(_iter_index_action(awaitables))
    assert three_element_list == action_sequence
    assert len(three_element_list) == 3

    three_element_list = list(_iter_index_action(awaitables, index=0))
    assert three_element_list == action_sequence
    assert len(three_element_list) == 3

    two_element_list = list(_iter_index_action(awaitables, index=1))
    assert two_element_list == action_sequence[1:]
    assert len(two_element_list) == 2

    one_element_list = list(_iter_index_action(awaitables, index=2))
    assert one_element_list == action_sequence[2:]
    assert len(one_element_list) == 1

    for out_of_bound_index in range(3, 10):
        zero_element_list = list(
            _iter_index_action(awaitables, index=out_of_bound_index)
        )
        assert zero_element_list == action_sequence[out_of_bound_index:]
        assert len(zero_element_list) == 0


@pytest.fixture
async def play_context(
    context: ContextIOInterface,
) -> PlayContext:
    play_context = PlayContext(
        context=context, app=FastAPI(), play_name="unique", scene_name="first"
    )
    await play_context.start()
    yield play_context
    await play_context.shutdown()


async def test_scene_player(
    play_context: PlayContext, caplog_info_level: LogCaptureFixture
):
    @mark_action
    async def initial() -> dict[str, Any]:
        print("initial")
        return {"x": 10, "y": 12.3}

    @mark_action
    async def verify(x: int, y: float) -> dict[str, Any]:
        assert type(x) == int
        assert type(y) == float
        return {"z": x + y}

    @mark_action
    async def print_second() -> dict[str, Any]:
        print("SECOND")
        return {}

    FIRST_STATE = Scene(
        name="first",
        actions=[
            initial,
            verify,
        ],
        next_scene="second",
        on_error_scene=None,
    )
    SECOND_STATE = Scene(
        name="second",
        actions=[
            print_second,
            verify,
            verify,
        ],
        next_scene=None,
        on_error_scene=None,
    )

    play_catalog = PlayCatalog(FIRST_STATE, SECOND_STATE)

    async def hook_before(scene: SceneName, action: ActionName) -> None:
        logger.info("hook_before %s %s", f"{scene=}", f"{action=}")

    async def hook_after(scene: SceneName, action: ActionName) -> None:
        logger.info("hook_after %s %s", f"{scene=}", f"{action=}")

    await scene_player(
        play_catalog=play_catalog,
        play_context=play_context,
        before_action_hook=hook_before,
        after_action_hook=hook_after,
    )

    # check hooks are working as expected
    assert "hook_before scene='first' action='initial'" in caplog_info_level.messages
    assert "hook_after scene='first' action='initial'" in caplog_info_level.messages


async def test_player_manager(context: ContextIOInterface):
    @mark_action
    async def initial_state() -> dict[str, Any]:
        print("initial state")
        return {"x": 10, "y": 12.3}

    @mark_action
    async def verify(x: int, y: float) -> dict[str, Any]:
        assert type(x) == int
        assert type(y) == float
        return {"z": x + y}

    @mark_action
    async def print_second() -> dict[str, Any]:
        print("SECOND")
        return {}

    FIRST_SCENE = Scene(
        name="first",
        actions=[
            initial_state,
            verify,
        ],
        next_scene="second",
        on_error_scene=None,
    )
    SECOND_SCENE = Scene(
        name="second",
        actions=[
            print_second,
            verify,
            verify,
        ],
        next_scene=None,
        on_error_scene=None,
    )

    play_catalog = PlayCatalog(FIRST_SCENE, SECOND_SCENE)

    play_manager = PlayerManager(
        context=context, app=FastAPI(), play_catalog=play_catalog
    )
    async with _player_manager_lifecycle(play_manager):
        # ok scene_player
        await play_manager.start_scene_player(
            play_name="start_first", scene_name="first"
        )
        assert "start_first" in play_manager._play_context
        assert "start_first" in play_manager._player_tasks
        await play_manager.wait_scene_player("start_first")
        assert "start_first" not in play_manager._play_context
        assert "start_first" not in play_manager._player_tasks

        # cancel scene_player
        await play_manager.start_scene_player(
            play_name="start_first", scene_name="first"
        )
        await play_manager.cancel_scene_player("start_first")
        assert "start_first" not in play_manager._play_context
        assert "start_first" not in play_manager._player_tasks
        with pytest.raises(PlayNotFoundException):
            await play_manager.wait_scene_player("start_first")


async def test_scene_player_error_handling(
    context: ContextIOInterface,
):
    ERROR_MARKER_IN_TB = "__this message must be present in the traceback__"

    @mark_action
    async def error_raiser() -> dict[str, Any]:
        raise RuntimeError(ERROR_MARKER_IN_TB)

    @mark_action
    async def graceful_error_handler(_exception: ExceptionInfo) -> dict[str, Any]:
        assert _exception.exception_class == RuntimeError
        assert _exception.scene_name in {"case_1_rasing_error", "case_2_rasing_error"}
        assert _exception.action_name == error_raiser.__name__
        assert ERROR_MARKER_IN_TB in _exception.serialized_traceback
        await asyncio.sleep(0.1)
        return {}

    # CASE 1
    # error is raised by first state, second state handles it -> no error raised
    CASE_1_RAISING_ERROR = Scene(
        name="case_1_rasing_error",
        actions=[
            error_raiser,
        ],
        next_scene=None,
        on_error_scene="case_1_handling_error",
    )
    CASE_1_HANDLING_ERROR = Scene(
        name="case_1_handling_error",
        actions=[
            graceful_error_handler,
        ],
        next_scene=None,
        on_error_scene=None,
    )

    # CASE 2
    # error is raised by first state -> raises error
    CASE_2_RASING_ERROR = Scene(
        name="case_2_raising_error",
        actions=[
            error_raiser,
        ],
        next_scene=None,
        on_error_scene=None,
    )

    play_catalog = PlayCatalog(
        CASE_1_RAISING_ERROR,
        CASE_1_HANDLING_ERROR,
        CASE_2_RASING_ERROR,
    )

    play_name = "test_play"
    # CASE 1
    player_manager = PlayerManager(
        context=context, app=FastAPI(), play_catalog=play_catalog
    )
    async with _player_manager_lifecycle(player_manager):
        await player_manager.start_scene_player(
            play_name=play_name, scene_name="case_1_rasing_error"
        )
        await player_manager.wait_scene_player(play_name)

    # CASE 2
    player_manager = PlayerManager(
        context=context, app=FastAPI(), play_catalog=play_catalog
    )
    async with _player_manager_lifecycle(player_manager):
        await player_manager.start_scene_player(
            play_name=play_name, scene_name="case_2_raising_error"
        )
        with pytest.raises(RuntimeError):
            await player_manager.wait_scene_player(play_name)
