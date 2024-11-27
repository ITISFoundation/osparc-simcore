# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

from typing import Callable, TypeVar, cast
from uuid import uuid4

from fastapi import FastAPI
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    DynamicServiceStart,
    DynamicServiceStop,
)
from models_library.api_schemas_webserver.projects_nodes import NodeGet
from models_library.projects_nodes_io import NodeID
from nicegui import ui
from nicegui.testing.user import User
from pydantic import TypeAdapter
from simcore_service_dynamic_scheduler.api.frontend.routes import marker_tags
from simcore_service_dynamic_scheduler.services.service_tracker import (
    set_if_status_changed_for_service,
    set_request_as_running,
    set_request_as_stopped,
)
from tenacity import AsyncRetrying, stop_after_delay, wait_fixed

T = TypeVar("T")

pytest_simcore_core_services_selection = [
    "rabbit",
    "redis",
]

pytest_simcore_ops_services_selection = [
    # "redis-commander",
]


def get_element(user: User, expected_type: type[T], *, tag: str) -> T:
    found_elements = list(user.find(tag).elements)
    assert len(found_elements) == 1
    result = found_elements[0]
    assert isinstance(result, expected_type)
    return result


def get_elements(user: User, expected_type: type[T], *, tag: str) -> list[T]:
    try:
        found_elements = list(user.find(tag).elements)
    except AssertionError:
        return []

    assert all(isinstance(entry, expected_type) for entry in found_elements)
    return cast(list[expected_type], found_elements)


def assert_count(user: User, expected_type: type[T], *, tag: str, count: int) -> None:
    assert len(get_elements(user, expected_type, tag=tag)) == count


async def wait_for_cards_to_render(user: User, *, count: int) -> None:
    async for attempt in AsyncRetrying(
        reraise=True, wait=wait_fixed(0.1), stop=stop_after_delay(2)
    ):
        with attempt:
            assert_count(
                user, ui.column, tag=marker_tags.INDEX_SERVICE_CARD, count=count
            )


async def test_index_with_elements(
    app: FastAPI,
    user: User,
    get_dynamic_service_start: Callable[[NodeID], DynamicServiceStart],
    get_dynamic_service_stop: Callable[[NodeID], DynamicServiceStop],
):
    await user.open("/")

    # 1. no tracked services
    assert get_element(user, ui.label, tag=marker_tags.INDEX_TOTAL_SERVICES_LABEL)
    assert (
        get_element(
            user, ui.label, tag=marker_tags.INDEX_TOTAL_SERVICES_COUNT_LABEL
        ).text
        == "0"
    )
    assert_count(user, ui.column, tag=marker_tags.INDEX_SERVICE_CARD, count=0)

    # 2. Add 2 services one stopped and one started
    await set_request_as_running(app, get_dynamic_service_start(uuid4()))
    await set_request_as_stopped(app, get_dynamic_service_stop(uuid4()))

    await wait_for_cards_to_render(user, count=2)

    assert (
        get_element(
            user, ui.label, tag=marker_tags.INDEX_TOTAL_SERVICES_COUNT_LABEL
        ).text
        == "2"
    )
    assert_count(user, ui.column, tag=marker_tags.INDEX_SERVICE_CARD, count=2)

    assert_count(
        user, ui.button, tag=marker_tags.INDEX_SERVICE_CARD_DETAILS_BUTTON, count=2
    )
    assert_count(
        user, ui.button, tag=marker_tags.INDEX_SERVICE_CARD_STOP_BUTTON, count=0
    )


async def test_index_stop_button(
    app: FastAPI,
    user: User,
    get_dynamic_service_start: Callable[[NodeID], DynamicServiceStart],
):
    await user.open("/")

    # insert a service
    new_style_node_id = uuid4()
    legacy_node_id = uuid4()

    await set_request_as_running(app, get_dynamic_service_start(new_style_node_id))
    await set_request_as_running(app, get_dynamic_service_start(legacy_node_id))

    # 1. No stop button rendered
    await wait_for_cards_to_render(user, count=2)
    assert_count(user, ui.column, tag=marker_tags.INDEX_SERVICE_CARD, count=2)
    assert_count(
        user, ui.button, tag=marker_tags.INDEX_SERVICE_CARD_DETAILS_BUTTON, count=2
    )
    assert_count(
        user, ui.button, tag=marker_tags.INDEX_SERVICE_CARD_STOP_BUTTON, count=0
    )

    # 2. Stop button appears
    # set the service status to running
    await set_if_status_changed_for_service(
        app,
        new_style_node_id,
        TypeAdapter(DynamicServiceGet).validate_python(
            DynamicServiceGet.model_config["json_schema_extra"]["examples"][0]
        ),
    )

    await set_if_status_changed_for_service(
        app,
        legacy_node_id,
        TypeAdapter(NodeGet).validate_python(
            NodeGet.model_config["json_schema_extra"]["examples"][0]
            | {"service_state": "running"}
        ),
    )

    # wait for stop buttons to appear
    async for attempt in AsyncRetrying(
        reraise=True, wait=wait_fixed(0.1), stop=stop_after_delay(2)
    ):
        with attempt:
            assert_count(
                user,
                ui.button,
                tag=marker_tags.INDEX_SERVICE_CARD_DETAILS_BUTTON,
                count=2,
            )
            assert_count(
                user, ui.button, tag=marker_tags.INDEX_SERVICE_CARD_STOP_BUTTON, count=2
            )
