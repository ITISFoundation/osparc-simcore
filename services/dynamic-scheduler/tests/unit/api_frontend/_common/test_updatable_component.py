# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

from functools import cached_property
from unittest.mock import Mock

import nicegui
import pytest
from fastapi import FastAPI
from helpers import assert_contains_text
from nicegui import APIRouter, ui
from playwright.async_api import Page
from pydantic import NonNegativeInt
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_dynamic_scheduler.api.frontend._common.base_display_model import (
    BaseUpdatableDisplayModel,
)
from simcore_service_dynamic_scheduler.api.frontend._common.updatable_component import (
    BaseUpdatableComponent,
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


@pytest.fixture
def router(person: "Person") -> APIRouter:
    router = APIRouter()

    @ui.page("/", api_router=router)
    async def index():
        _index_page_ui(person)

    return router


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
        minimal_app, mount_path=mount_path, storage_secret="test-secret"
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
    def add_to_ui(self) -> None:
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
    def add_to_ui(self) -> None:
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
    def add_to_ui(self) -> None:
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
                FriendComponent(self.display_model.companion).add_to_ui()

            elif isinstance(self.display_model.companion, Pet):
                PetComponent(self.display_model.companion).add_to_ui()

        _friend_or_pet_ui()
        self.display_model.on_type_change("companion", _friend_or_pet_ui.refresh)


def _index_page_ui(person: Person) -> None:
    ui.label("BEFORE_LABEL")
    PersonComponent(person).add_to_ui()
    ui.label("AFTER_LABEL")


async def _ensure_before_label(async_page: Page) -> None:
    await assert_contains_text(async_page, "BEFORE_LABEL")


async def _ensure_person_name(async_page: Page, name: str) -> None:
    await assert_contains_text(async_page, f"Name: {name}")


async def _ensure_person_age(async_page: Page, age: int) -> None:
    await assert_contains_text(async_page, f"Age: {age}")


async def _esnure_person_companion(async_page: Page, companion: Pet | Friend) -> None:
    if isinstance(companion, Pet):
        await assert_contains_text(async_page, f"Pet Name: {companion.name}")
        await assert_contains_text(async_page, f"Pet Species: {companion.species}")
    elif isinstance(companion, Friend):
        await assert_contains_text(async_page, f"Friend Name: {companion.name}")
        await assert_contains_text(async_page, f"Friend Age: {companion.age}")


async def _ensure_after_label(async_page: Page) -> None:
    await assert_contains_text(async_page, "AFTER_LABEL")


async def _ensure_index_page(async_page: Page, person: Person) -> None:
    await _ensure_before_label(async_page)

    await _ensure_person_name(async_page, person.name)
    await _ensure_person_age(async_page, person.age)

    await _esnure_person_companion(async_page, person.companion)

    await _ensure_after_label(async_page)


@pytest.mark.parametrize(
    "person, person_update, expected_callbacks_count",
    [
        pytest.param(
            Person(name="Alice", age=30, companion=Pet(name="Fluffy", species="cat")),
            Person(name="Alice", age=30, companion=Pet(name="Buddy", species="dog")),
            0,
            id="update-pet-via-attribute-biding-no-rerender",
        ),
        pytest.param(
            Person(name="Alice", age=30, companion=Pet(name="Fluffy", species="cat")),
            Person(name="Alice", age=30, companion=Friend(name="Marta", age=30)),
            1,
            id="update-pet-ui-via-rerednder-due-to-type-change",
        ),
        pytest.param(
            Person(name="Alice", age=30, companion=Pet(name="Fluffy", species="cat")),
            Person(name="Bob", age=30, companion=Pet(name="Fluffy", species="cat")),
            0,
            id="change-person-name-via-bindings",
        ),
        pytest.param(
            Person(name="Alice", age=30, companion=Pet(name="Fluffy", species="cat")),
            Person(name="Alice", age=31, companion=Pet(name="Fluffy", species="cat")),
            1,
            id="change-person-age-via-rerender-due-to-value-change",
        ),
    ],
)
async def test_updatable_component(
    app_runner: None,
    async_page: Page,
    mount_path: str,
    server_host_port: str,
    person: Person,
    person_update: Person,
    expected_callbacks_count: NonNegativeInt,
):
    await async_page.goto(f"{server_host_port}{mount_path}")

    # check initial page layout
    await _ensure_index_page(async_page, person)

    callbacks_count = person.update(person_update)
    assert callbacks_count == expected_callbacks_count

    # change layout after update
    await _ensure_index_page(async_page, person_update)
