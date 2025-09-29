# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

from collections.abc import Awaitable, Callable
from functools import cached_property
from unittest.mock import Mock

import nicegui
import pytest
from fastapi import FastAPI
from helpers import assert_contains_text, assert_not_contains_text
from nicegui import APIRouter, ui
from playwright.async_api import Page
from pydantic import NonNegativeInt
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_dynamic_scheduler.api.frontend._common.base_component import (
    BaseUpdatableComponent,
)
from simcore_service_dynamic_scheduler.api.frontend._common.base_display_model import (
    BaseUpdatableDisplayModel,
)
from simcore_service_dynamic_scheduler.api.frontend._common.stack import (
    UpdatableComponentStack,
)
from simcore_service_dynamic_scheduler.api.frontend._utils import set_parent_app


@pytest.fixture
def app_environment() -> EnvVarsDict:
    return {}


@pytest.fixture
def mount_path() -> str:
    return "/dynamic-scheduler/"


@pytest.fixture
def use_internal_scheduler() -> bool:
    return True


class LayoutManager:
    def __init__(self) -> None:
        self._draw_ui: Callable[[], None] | None = None

    def set(self, draw_ui: Callable[[], None]) -> None:
        self._draw_ui = draw_ui

    def draw(self) -> None:
        if self._draw_ui is not None:
            self._draw_ui()


@pytest.fixture
def layout_manager() -> LayoutManager:
    return LayoutManager()


@pytest.fixture
def router(layout_manager: LayoutManager) -> APIRouter:
    router = APIRouter()

    @ui.page("/", api_router=router)
    async def index():
        ui.label("BEFORE_CORPUS")
        layout_manager.draw()
        ui.label("AFTER_CORPUS")

    return router


@pytest.fixture
def ensure_page_loaded(
    async_page: Page,
    server_host_port: str,
    mount_path: str,
    layout_manager: LayoutManager,
) -> Callable[[Callable[[], None]], Awaitable[None]]:
    async def _(draw_ui: Callable[[], None]) -> None:
        layout_manager.set(draw_ui)
        await async_page.goto(f"{server_host_port}{mount_path}")
        await _ensure_before_corpus(async_page)
        await _ensure_after_corpus(async_page)
        print("✅ index page loaded")

    return _


@pytest.fixture
def not_initialized_app(
    reset_nicegui_app: None,
    app_environment: EnvVarsDict,
    router: APIRouter,
    mount_path: str,
) -> FastAPI:
    minimal_app = FastAPI()

    mock_settings = Mock()
    mock_settings.DYNAMIC_SCHEDULER_UI_MOUNT_PATH = mount_path
    minimal_app.state.settings = mock_settings

    nicegui.app.include_router(router)

    nicegui.ui.run_with(
        minimal_app, mount_path=mount_path, storage_secret="test-secret"  # noqa: S106
    )
    set_parent_app(minimal_app)
    return minimal_app


class Pet(BaseUpdatableDisplayModel):
    name: str
    species: str


class Friend(BaseUpdatableDisplayModel):
    name: str
    age: int


class Person(BaseUpdatableDisplayModel):
    @cached_property
    def rerender_on_type_change(self) -> set[str]:
        return {"companion"}

    name: str
    age: int
    companion: Pet | Friend


class FriendComponent(BaseUpdatableComponent[Friend]):
    def _draw_ui(self) -> None:
        ui.label().bind_text_from(
            self.display_model,
            "name",
            backward=lambda name: f"Friend Name: {name}",
        )
        ui.label().bind_text_from(
            self.display_model,
            "age",
            backward=lambda age: f"Friend Age: {age}",
        )


class PetComponent(BaseUpdatableComponent[Pet]):
    def _draw_ui(self) -> None:
        ui.label().bind_text_from(
            self.display_model,
            "name",
            backward=lambda name: f"Pet Name: {name}",
        )
        ui.label().bind_text_from(
            self.display_model,
            "species",
            backward=lambda species: f"Pet Species: {species}",
        )


class PersonComponent(BaseUpdatableComponent[Person]):
    def _draw_ui(self) -> None:
        with ui.element().classes("border"):
            # NOTE:
            # There are 3 ways to bind the UI to the model changes:
            # 1. using nicegui builting facilties
            # 2. via model attribute VALE change
            # 3. via model attribute TYPE change
            # The model attribute changes allow to trigger re-rendering of subcomponents.
            # This should be mainly used for chainging the UI layout based on
            # the attribute's value or type.

            # 1. bind the label directly to the model's attribute
            ui.label().bind_text_from(
                self.display_model,
                "name",
                backward=lambda name: f"Name: {name}",
            )

            # 2. use refreshable and bind to the attribute's VALUE change
            @ui.refreshable
            def _person_age_ui() -> None:
                ui.label(f"Age: {self.display_model.age}")

            _person_age_ui()
            self.display_model.on_value_change("age", _person_age_ui.refresh)

            # 3. use refreshable and bind to the attribute's TYPE change
            @ui.refreshable
            def _friend_or_pet_ui() -> None:
                if isinstance(self.display_model.companion, Friend):
                    FriendComponent(self.display_model.companion).display()

                elif isinstance(self.display_model.companion, Pet):
                    PetComponent(self.display_model.companion).display()

            _friend_or_pet_ui()
            self.display_model.on_type_change("companion", _friend_or_pet_ui.refresh)


async def _ensure_before_corpus(async_page: Page) -> None:
    await assert_contains_text(async_page, "BEFORE_CORPUS")


async def _ensure_person_companion(async_page: Page, companion: Pet | Friend) -> None:
    if isinstance(companion, Pet):
        await assert_contains_text(async_page, f"Pet Name: {companion.name}")
        await assert_contains_text(async_page, f"Pet Species: {companion.species}")
    elif isinstance(companion, Friend):
        await assert_contains_text(async_page, f"Friend Name: {companion.name}")
        await assert_contains_text(async_page, f"Friend Age: {companion.age}")


async def _ensure_after_corpus(async_page: Page) -> None:
    await assert_contains_text(async_page, "AFTER_CORPUS")


async def _ensure_person_is_present(async_page: Page, person: Person) -> None:
    await _ensure_before_corpus(async_page)

    await assert_contains_text(async_page, f"Name: {person.name}")
    await assert_contains_text(async_page, f"Age: {person.age}")

    await _ensure_person_companion(async_page, person.companion)

    await _ensure_after_corpus(async_page)


async def _ensure_companion_not_present(
    async_page: Page, companion: Pet | Friend
) -> None:
    if isinstance(companion, Pet):
        await assert_not_contains_text(async_page, f"Pet Name: {companion.name}")
        await assert_not_contains_text(async_page, f"Pet Species: {companion.species}")
    elif isinstance(companion, Friend):
        await assert_not_contains_text(async_page, f"Friend Name: {companion.name}")
        await assert_not_contains_text(async_page, f"Friend Age: {companion.age}")


async def _ensure_person_not_present(async_page: Page, person: Person) -> None:
    await _ensure_before_corpus(async_page)

    await assert_not_contains_text(async_page, f"Name: {person.name}")
    await assert_not_contains_text(async_page, f"Age: {person.age}")

    await _ensure_companion_not_present(async_page, person.companion)

    await _ensure_after_corpus(async_page)


def _get_updatable_display_model_ids(obj: BaseUpdatableDisplayModel) -> dict[int, str]:
    result: dict[int, str] = {id(obj): obj.__class__.__name__}
    for value in obj.__dict__.values():
        if isinstance(value, BaseUpdatableDisplayModel):
            result[id(value)] = value.__class__.__name__
    return result


@pytest.mark.parametrize(
    "person, person_update, expect_same_companion_object, expected_callbacks_count",
    [
        pytest.param(
            Person(name="Alice", age=30, companion=Pet(name="Fluffy", species="cat")),
            Person(name="Alice", age=30, companion=Pet(name="Buddy", species="dog")),
            True,
            0,
            id="update-pet-via-attribute-biding-no-rerender",
        ),
        pytest.param(
            Person(name="Alice", age=30, companion=Pet(name="Fluffy", species="cat")),
            Person(name="Alice", age=30, companion=Friend(name="Marta", age=30)),
            False,
            1,
            id="update-pet-ui-via-rerednder-due-to-type-change",
        ),
        pytest.param(
            Person(name="Alice", age=30, companion=Pet(name="Fluffy", species="cat")),
            Person(name="Bob", age=30, companion=Pet(name="Fluffy", species="cat")),
            True,
            0,
            id="change-person-name-via-bindings",
        ),
        pytest.param(
            Person(name="Alice", age=30, companion=Pet(name="Fluffy", species="cat")),
            Person(name="Alice", age=31, companion=Pet(name="Fluffy", species="cat")),
            True,
            1,
            id="change-person-age-via-rerender-due-to-value-change",
        ),
    ],
)
async def test_updatable_component(
    app_runner: None,
    ensure_page_loaded: Callable[[Callable[[], None]], Awaitable[None]],
    async_page: Page,
    person: Person,
    person_update: Person,
    expect_same_companion_object: bool,
    expected_callbacks_count: NonNegativeInt,
):
    def _index_corpus() -> None:
        PersonComponent(person).display()

    await ensure_page_loaded(_index_corpus)

    # check initial page layout
    await _ensure_person_is_present(async_page, person)

    before_update = _get_updatable_display_model_ids(person)
    callbacks_count = person.update(person_update)
    after_update = _get_updatable_display_model_ids(person)
    assert (before_update == after_update) is expect_same_companion_object

    assert callbacks_count == expected_callbacks_count

    # change layout after update
    await _ensure_person_is_present(async_page, person_update)

    # REMOVE only the companion form UI
    person.companion.remove_from_ui()
    await _ensure_companion_not_present(async_page, person.companion)

    # REMOVE the person form UI
    person.remove_from_ui()
    await _ensure_person_not_present(async_page, person)

    await _ensure_before_corpus(async_page)
    await _ensure_after_corpus(async_page)


async def test_multiple_componenets_management(
    app_runner: None,
    ensure_page_loaded: Callable[[Callable[[], None]], Awaitable[None]],
    async_page: Page,
):
    stack = UpdatableComponentStack[Person](PersonComponent)

    def _index_corpus() -> None:
        stack.display()

    await ensure_page_loaded(_index_corpus)

    person_1 = Person(name="Alice", age=30, companion=Pet(name="Fluffy", species="cat"))
    person_2 = Person(name="Bob", age=25, companion=Friend(name="Marta", age=28))

    # nothing is displayed
    await _ensure_person_not_present(async_page, person_1)
    await _ensure_person_not_present(async_page, person_2)

    stack.add_or_update_model("person_1", person_1)
    stack.add_or_update_model("person_2", person_2)

    # both persons are displayed
    await _ensure_person_is_present(async_page, person_1)
    await _ensure_person_is_present(async_page, person_2)

    # only person_2 is displayed
    stack.remove_model("person_1")
    await _ensure_person_not_present(async_page, person_1)
    await _ensure_person_is_present(async_page, person_2)

    # no person is displayed
    stack.remove_model("person_2")
    await _ensure_person_not_present(async_page, person_2)
    await _ensure_person_not_present(async_page, person_1)

    # add both persons again together
    stack.update_from_dict({"person_1": person_1, "person_2": person_2})
    await _ensure_person_is_present(async_page, person_1)
    await _ensure_person_is_present(async_page, person_2)

    # only person_1 is displayed
    stack.update_from_dict({"person_1": person_1})
    await _ensure_person_is_present(async_page, person_1)
    await _ensure_person_not_present(async_page, person_2)

    # no person is displayed
    stack.update_from_dict({})
    await _ensure_person_not_present(async_page, person_1)
    await _ensure_person_not_present(async_page, person_2)
