from typing import Any

import pytest
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._errors import (
    NextSceneNotInPlayCatalogException,
    OnErrorSceneNotInPlayCatalogException,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._marker import (
    mark_step,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._scene import (
    PlayCatalog,
    Scene,
)


async def test_scene_ok():
    @mark_step
    async def print_info() -> dict[str, Any]:
        print("some info")
        return {}

    @mark_step
    async def verify(x: float, y: int) -> dict[str, Any]:
        assert type(x) == float
        assert type(y) == int
        return {}

    INFO_CHECK = Scene(
        name="test",
        steps=[
            print_info,
            verify,
        ],
        next_scene=None,
        on_error_scene=None,
    )
    assert INFO_CHECK


def test_play_catalog():
    SCENE_ONE_NAME = "one"
    SCENE_TWO_NAME = "two"
    SCENE_MISSING_NAME = "not_existing_scene"

    scene_one = Scene(
        name=SCENE_ONE_NAME, steps=[], next_scene=None, on_error_scene=None
    )
    scene_two = Scene(
        name=SCENE_TWO_NAME, steps=[], next_scene=None, on_error_scene=None
    )

    play_catalog = PlayCatalog(
        scene_one,
        scene_two,
    )

    # in operator
    assert SCENE_ONE_NAME in play_catalog
    assert SCENE_TWO_NAME in play_catalog
    assert SCENE_MISSING_NAME not in play_catalog

    # get key operator
    assert play_catalog[SCENE_ONE_NAME] == scene_one
    assert play_catalog[SCENE_TWO_NAME] == scene_two
    with pytest.raises(KeyError):
        play_catalog[SCENE_MISSING_NAME]  # pylint:disable=pointless-statement


def test_play_catalog_missing_next_scene():
    scene = Scene(
        name="some_name",
        steps=[],
        next_scene="missing_next_scene",
        on_error_scene=None,
    )
    with pytest.raises(NextSceneNotInPlayCatalogException):
        PlayCatalog(scene)


def test_play_catalog_missing_on_error_scene():
    scene = Scene(
        name="some_name",
        steps=[],
        next_scene=None,
        on_error_scene="missing_on_error_scene",
    )
    with pytest.raises(OnErrorSceneNotInPlayCatalogException):
        PlayCatalog(scene)
