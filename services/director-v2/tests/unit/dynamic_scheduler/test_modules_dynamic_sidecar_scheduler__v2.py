"""
Problem: `Baking a chocolate cake`.

When following a recipe all should be relatively simple,
but in reality unexpected things can happen:
- the oven you are using can be faulty
- you can run out of ingredients
- you might not have enough time to finish
- you can be interrupted by something more urgent

---
Breakdown of the above problem in simple steps

Step 1 `buy ingredients`:
- go to the store and buy required ingredients

Step 2 `prepare mixture`:
- get correct ingredient amounts (ingredients can be insufficient, you
have to get some more)
- mix the ingredients

Step 3 `bake cake`:
- butter tin
- bake cake in the oven (the oven could burn the cake, you have to try again)

Step 4 `enjoy the cake`:
- take nice picture of the cake
- eat the cake

Expected outcomes:
1. baking finishes without issues
2. did not finish baking and have to retry for several reasons
3. get interrupted by an urgent phone call and have to cancel

---
`Scenes` and `actions` required to describe above:

Scene `initial_setup`:
- `actions`:
    - shop for ingredients
- `next_scene`: `preparation`
- `on_error_scene`: None

Scene `preparation`:
- `actions`:
    - get correct amounts of ingredients
    - mix ingredients
- `next_scene`: `baking`
- `on_error_scene`: `error_out_of_ingredients`

Scene `baking`:
- `actions`:
    - butter tin
    - bake in faulty oven (probability of fail 65%)
- `next_scene`: `eat_cake`
- `on_error_scene`: `error_cake_burned`

Scene `eat_cake`:
- `actions`:
    - take picture of cake
    - eat it (finished successfully) :+1:
- `next_scene`: None
- `on_error_scene`: None

Scene `error_cake_burned`:
- `actions`:
    - take note of your error
    - `next_scene`: `preparation` (try to bake cake again with remaining ingredients)
- `on_error_scene`: None

Scene `error_out_of_ingredients`:
- `actions`:
    - if no more time remains raise an error and stop here :-1:
- `next_scene`: `initial_setup` (start form scratch again)
- `on_error_scene`: None

"""

# pylint: disable=protected-access
# pylint: disable=redefined-outer-name

import asyncio
import logging
import random
from typing import Any
from unittest.mock import AsyncMock

import pytest
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2 import (
    PlayCatalog,
    PlayerManager,
    Scene,
    mark_action,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._context_base import (
    ContextInterface,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._models import (
    PlayName,
)

logger = logging.getLogger(__name__)


# BAKE CAKE


class FailedToBakeCakeError(Exception):
    ...


class NotEnoughIngredientsError(Exception):
    ...


class SceneNames:
    INITIAL_SETUP = "initial_setup"
    PREPARATION = "preparation"
    BAKING = "baking"
    EAT_CAKE = "eat_cake"

    ERROR_CAKE_BURNT = "error_cake_burnt"
    ERROR_OUT_OF_INGREDIENTS = "error_out_of_ingredients"


@mark_action
async def shop_for_ingredients() -> dict[str, Any]:
    return {"cake_mix_kg": 1.0, "butter_g": 100}


@mark_action
async def get_correct_amount_fo_ingredients(
    cake_mix_kg: float, butter_g: int
) -> dict[str, Any]:
    cake_mix_kg -= 0.25
    butter_g -= 8

    # check remaining ingredients are not finished!!!
    assert cake_mix_kg >= 0.0
    assert butter_g >= 0.0

    remaining_supplies = dict(cake_mix_kg=cake_mix_kg, butter_g=butter_g)
    logger.info("%s", f"{remaining_supplies}")
    return remaining_supplies


@mark_action
async def mix_ingredients() -> dict[str, Any]:
    logger.info("mixing ingredients...")
    return {}


@mark_action
async def butter_tin() -> dict[str, Any]:
    logger.info("buttering tin...")
    return {}


@mark_action
async def bake_cake_in_oven(available_time_hours: float) -> dict[str, Any]:
    available_time_hours -= 1.0
    return dict(available_time_hours=available_time_hours)


@mark_action
async def check_bake_result(oven_fail_probability: float) -> dict[str, Any]:
    assert 0 <= oven_fail_probability <= 1
    fails = int(oven_fail_probability * 100)
    success = 100 - fails
    assert fails + success == 100

    bake_outcomes: list[bool] = [True] * success + [False] * fails
    bake_successful = random.choice(bake_outcomes)
    if not bake_successful:
        raise FailedToBakeCakeError("could not bake cake")
    return {}


@mark_action
async def take_picture_of_cake() -> dict[str, Any]:
    logger.info("snapped cake pic!")
    return {}


@mark_action
async def eat_cake() -> dict[str, Any]:
    logger.info("eating cake...")
    return {}


@mark_action
async def take_note_of_the_error() -> dict[str, Any]:
    logger.info("oven failed to bake cake, will try again")
    return {}


@mark_action
async def check_if_still_have_time(available_time_hours: float) -> dict[str, Any]:
    if available_time_hours < 1.0:
        raise NotEnoughIngredientsError("did not have enough time to finish")
    return {}


PLAY_CATALOG = PlayCatalog(
    Scene(
        name=SceneNames.INITIAL_SETUP,
        actions=[
            shop_for_ingredients,
        ],
        next_scene=SceneNames.PREPARATION,
        on_error_scene=None,
    ),
    Scene(
        name=SceneNames.PREPARATION,
        actions=[
            get_correct_amount_fo_ingredients,
            mix_ingredients,
        ],
        next_scene=SceneNames.BAKING,
        on_error_scene=SceneNames.ERROR_OUT_OF_INGREDIENTS,
    ),
    Scene(
        name=SceneNames.BAKING,
        actions=[
            butter_tin,
            bake_cake_in_oven,
            check_bake_result,
        ],
        next_scene=SceneNames.EAT_CAKE,
        on_error_scene=SceneNames.ERROR_CAKE_BURNT,
    ),
    Scene(
        name=SceneNames.EAT_CAKE,
        actions=[
            take_picture_of_cake,
            eat_cake,
        ],
        next_scene=None,
        on_error_scene=None,
    ),
    Scene(
        name=SceneNames.ERROR_CAKE_BURNT,
        actions=[
            take_note_of_the_error,
        ],
        next_scene=SceneNames.PREPARATION,
        on_error_scene=None,
    ),
    Scene(
        name=SceneNames.ERROR_OUT_OF_INGREDIENTS,
        actions=[
            check_if_still_have_time,
        ],
        next_scene=SceneNames.INITIAL_SETUP,
        on_error_scene=None,
    ),
)

# FIXTURES


@pytest.fixture
def app() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def play_name() -> PlayName:
    return "test_play_name"


@pytest.fixture
async def player_manager(app: AsyncMock, context: ContextInterface) -> PlayerManager:
    player_manager = PlayerManager(context=context, app=app, play_catalog=PLAY_CATALOG)
    await player_manager.setup()
    yield player_manager
    await player_manager.teardown()


# TESTS


async def test_bake_cake_ok_eventually(
    player_manager: PlayerManager, context: ContextInterface, play_name: PlayName
):
    # Before the baking, initiate some vars in the context
    # to be available (this is just a convenient place do to it)
    await context.save("available_time_hours", 10.0)
    await context.save("oven_fail_probability", 0.65)

    # With an over fail probability of 65% and 10 tries to bake a cake
    # we expect for the procedure to eventually finish without issues
    await player_manager.start_scene_player(
        play_name=play_name, scene_name=SceneNames.INITIAL_SETUP
    )

    # waiting here is done for convenience, normally you would not do this
    await player_manager.wait_scene_player(play_name)


async def test_bake_cake_fails(
    player_manager: PlayerManager, context: ContextInterface, play_name: PlayName
):
    await context.save("available_time_hours", 10.0)
    await context.save("oven_fail_probability", 1.0)

    # With an over fail probability of 100% it is not possible to
    # finish baking the cake in time, after 10 tries it will give up
    # and raise an error.
    await player_manager.start_scene_player(
        play_name=play_name, scene_name=SceneNames.INITIAL_SETUP
    )
    with pytest.raises(NotEnoughIngredientsError):
        await player_manager.wait_scene_player(play_name)


async def test_bake_cake_cancelled_by_external_event(
    player_manager: PlayerManager, context: ContextInterface, play_name: PlayName
):
    await context.save("available_time_hours", 1e10)
    await context.save("oven_fail_probability", 1.0)

    # With a virtually infinite time to spend for retries
    # event if the over fail probability is 100% this process
    # will last a very long time before failing.
    await player_manager.start_scene_player(
        play_name=play_name, scene_name=SceneNames.INITIAL_SETUP
    )
    ENSURE_IT_IS_RUNNING = 0.1
    await asyncio.sleep(ENSURE_IT_IS_RUNNING)

    # Emulating that a technician just rang the dor bell
    # to fix the faulty oven. Cancelling current task
    assert play_name in player_manager._player_tasks
    await player_manager.cancel_scene_player(play_name)
    assert play_name not in player_manager._player_tasks

    # Technician fixes oven, a new task or the same one can
    # be started again. Expect to finish immediately since
    # there is a 0% probability of oven failure.
    await context.save("oven_fail_probability", 0.0)
    await player_manager.start_scene_player(
        play_name=play_name, scene_name=SceneNames.INITIAL_SETUP
    )
    await player_manager.wait_scene_player(play_name)
