# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

from copy import deepcopy
from functools import cached_property

import nicegui
import pytest
from fastapi import FastAPI
from helpers import assert_contains_text
from nicegui import APIRouter, ui
from playwright.async_api import Page
from simcore_service_dynamic_scheduler.api.frontend._common.base_display_model import (
    BaseUpdatableDisplayModel,
)
from simcore_service_dynamic_scheduler.api.frontend._common.updatable_component import (
    BaseUpdatableComponent,
)
from simcore_service_dynamic_scheduler.api.frontend._utils import (
    get_settings,
    set_parent_app,
)
from simcore_service_dynamic_scheduler.core.settings import ApplicationSettings

pytest_simcore_core_services_selection = [
    "postgres",
    "rabbit",
    "redis",
]

pytest_simcore_ops_services_selection = [
    "redis-commander",
]


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
        ui.label(f"Name: {self.display_model.name}")
        ui.label(f"Age: {self.display_model.age}")

        @ui.refreshable
        def _friend_or_pet_ui() -> None:
            if isinstance(self.display_model.companion, Friend):
                FriendComponent(self.display_model.companion).add_to_ui()

            elif isinstance(self.display_model.companion, Pet):
                PetComponent(self.display_model.companion).add_to_ui()

        _friend_or_pet_ui()

        # self.display_model.on_value_change("companion", comp_ui.refresh)
        self.display_model.on_type_change("companion", _friend_or_pet_ui.refresh)


def _index_page_ui(person: Person) -> None:
    ui.label("BEFORE_LABEL")
    PersonComponent(person).add_to_ui()
    ui.label("AFTER_LABEL")


@pytest.fixture
def use_internal_scheduler() -> bool:
    return True


@pytest.fixture
def router(person: Person) -> APIRouter:
    router = APIRouter()

    @ui.page("/", api_router=router)
    async def index():
        _index_page_ui(person)

    return router


@pytest.fixture
def not_initialized_app(not_initialized_app: FastAPI, router: APIRouter) -> FastAPI:
    minimal_app = FastAPI()

    settings = ApplicationSettings.create_from_envs()
    minimal_app.state.settings = settings

    nicegui.app.include_router(router)

    nicegui.ui.run_with(
        minimal_app,
        mount_path=settings.DYNAMIC_SCHEDULER_UI_MOUNT_PATH,
        storage_secret=settings.DYNAMIC_SCHEDULER_UI_STORAGE_SECRET.get_secret_value(),
    )
    set_parent_app(minimal_app)
    return minimal_app


async def _ensure_before_label(async_page: Page) -> None:
    await assert_contains_text(async_page, "BEFORE_LABEL")


async def _ensure_after_label(async_page: Page) -> None:
    await assert_contains_text(async_page, "AFTER_LABEL")


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


@pytest.mark.parametrize(
    "person, expected",
    [
        pytest.param(
            Person(name="Alice", age=30, companion=Pet(name="Fluffy", species="cat")),
            True,
            id="initial-test",
        )
    ],
)
async def test_updatable_component(
    app_runner: None,
    async_page: Page,
    server_host_port: str,
    person: Person,
    expected: bool,
):
    await async_page.goto(
        f"{server_host_port}{get_settings().DYNAMIC_SCHEDULER_UI_MOUNT_PATH}"
    )

    # INITIAL RENDER
    await _ensure_before_label(async_page)
    await _ensure_after_label(async_page)

    await _ensure_person_name(async_page, person.name)
    await _ensure_person_age(async_page, person.age)
    await _esnure_person_companion(async_page, person.companion)

    # AFTER CHNGE RENDER

    # # TODO: test that it changes when accessing the propeties directly

    await assert_contains_text(async_page, "Pet Name: Fluffy")
    person.companion.name = "Buddy"
    await assert_contains_text(async_page, "Pet Name: Buddy")

    # # TODO: check that UI was rerendered with new pet name

    # person.name = "Bob"
    # # TODO: check that UI was rerendered with new name

    # person.companion = Pet(name="Buddy", species="dog")
    # # TODO: check that ui has no changes only values changed

    # on_value_cahnge rerender
    # simulate an update from a new incoming object in memory

    person_update = deepcopy(person)
    person_update.companion = Friend(name="Charlie", age=25)

    person.update(person_update)
    await assert_contains_text(async_page, "Friend Name: Charlie", timeout=2)

    # TODO: on type change rerender

    # # TODO: test that it changes if we apply the updates via the update method on the object?

    # # TODO: check that ui has changed as expected
    # assert person.requires_rerender({"age": 31}) is False
    # person_display.update_model({"age": 31})

    # # TODO: check that ui has changed as expected
    # assert person.requires_rerender({"companion": {"name": "Daisy"}}) is False
    # person_display.update_model({"companion": {"name": "Daisy"}})

    # # TODO: check that ui has changed as expected
    # assert person.requires_rerender({"companion": {"age": 28}}) is False
    # person_display.update_model({"companion": {"name": "Eve", "age": 28}})


# TODO: make tests go faster since we are running differently
