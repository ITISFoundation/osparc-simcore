# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

from functools import cached_property

import nicegui
import pytest
from fastapi import FastAPI
from helpers import assert_contains_text
from nicegui import APIRouter, ui
from nicegui.element import Element
from playwright.async_api import Page
from pytest_mock import MockerFixture
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


class PersonDisplay(BaseUpdatableComponent[Person]):
    def _get_parent(self) -> Element:
        return ui.column()

    def _draw(self) -> None:
        print("calling _draw")
        ui.label(f"Name: {self.display_model.name}")
        ui.label(f"Age: {self.display_model.age}")

        @ui.refreshable
        def comp_ui() -> None:
            if isinstance(self.display_model.companion, Friend):
                ui.label().bind_text_from(
                    self.display_model.companion,
                    "name",
                    backward=lambda name: f"Friend Name: {name}",
                )
                ui.label(f"Friend Age: {self.display_model.companion.age}")

            if isinstance(self.display_model.companion, Pet):
                ui.label().bind_text_from(
                    self.display_model.companion,
                    "name",
                    backward=lambda name: f"Pet Name: {name}",
                )
                ui.label(f"Pet Species: {self.display_model.companion.species}")

        comp_ui()

        # self.display_model.on_value_change("companion", comp_ui.refresh)
        self.display_model.on_type_change("companion", comp_ui.refresh)


@pytest.fixture
def use_internal_scheduler() -> bool:
    return True


@pytest.fixture
def person() -> Person:
    return Person(name="Alice", age=30, companion=Pet(name="Fluffy", species="cat"))


@pytest.fixture
def router(person: Person) -> APIRouter:

    router = APIRouter()

    @ui.page("/", api_router=router)
    async def index():
        person_display = PersonDisplay(person)

        ui.label("BEFORE_LABEL")
        person_display.add_to_ui()
        ui.label("AFTER_LABEL")

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


async def test_updatable_component(
    mocker: MockerFixture,
    app_runner: None,
    async_page: Page,
    server_host_port: str,
    person: Person,
    # person_display: PersonDisplay,
):
    await async_page.goto(
        f"{server_host_port}{get_settings().DYNAMIC_SCHEDULER_UI_MOUNT_PATH}"
    )

    # ensre render worked
    await assert_contains_text(async_page, "BEFORE_LABEL")
    await assert_contains_text(async_page, "AFTER_LABEL")

    await assert_contains_text(async_page, "Name: Alice")
    await assert_contains_text(async_page, "Age: 30")

    # _draw_spy = mocker.spy(person_display, "_draw")
    # _recreate_ui_spy = mocker.spy(person_display, "_recrate_ui")

    # # TODO: test that it changes when accessing the propeties directly

    await assert_contains_text(async_page, "Pet Name: Fluffy")
    person.companion.name = "Buddy"
    # : TODO: bidn property
    await assert_contains_text(async_page, "Pet Name: Buddy", timeout=2)

    # # TODO: check that UI was rerendered with new pet name

    # person.name = "Bob"
    # # TODO: check that UI was rerendered with new name

    # person.companion = Pet(name="Buddy", species="dog")
    # # TODO: check that ui has no changes only values changed

    person.companion = Friend(name="Charlie", age=25)
    await assert_contains_text(async_page, "Friend Name: Charlie2", timeout=2)

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
