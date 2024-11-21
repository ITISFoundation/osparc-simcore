import asyncio
import json
from abc import ABC, abstractmethod
from collections.abc import AsyncIterable
from typing import Any, TypeAlias
from weakref import WeakSet

from fastapi import FastAPI
from fastui import AnyComponent, FastUI
from pydantic import NonNegativeFloat, TypeAdapter
from servicelib.fastapi.app_state import SingletonInAppStateMixin

UpdateID: TypeAlias = int


class AbstractSSERenderer(ABC):
    def __init__(self) -> None:
        self._items: list[Any] = []

    def update(self, items: list[Any]) -> None:
        self._items = items

    def _get_update_id(self) -> UpdateID:
        return hash(json.dumps(TypeAdapter(list[Any]).validate_python(self._items)))

    def changes_detected(self, last_update_id: UpdateID) -> bool:
        return last_update_id != self._get_update_id()

    @staticmethod
    @abstractmethod
    def render_item(item: Any) -> AnyComponent:
        """return a rendered component to display"""

    def get_messages(self) -> tuple[UpdateID, list[AnyComponent]]:
        return self._get_update_id(), [self.render_item(x) for x in self._items]


class RendererManager(SingletonInAppStateMixin):
    app_state_name: str = "renderer_manager"
    """Allows to register SSE renderers and distribute data based on type"""

    def __init__(self) -> None:
        self._renderers: dict[
            type[AbstractSSERenderer], WeakSet[AbstractSSERenderer]
        ] = {}

    def register_renderer(self, renderer: AbstractSSERenderer) -> None:
        """NOTE: there is no reason to unregister anything due to WeakSet tracking"""
        renderer_type = type(renderer)

        if renderer_type not in self._renderers:
            self._renderers[renderer_type] = WeakSet()

        self._renderers[renderer_type].add(renderer)

    def update_renderer(
        self, renderer_type: type[AbstractSSERenderer], items: list[Any]
    ) -> None:
        """propagate updates to all instances of said type SSERenderer"""
        for renderer in self._renderers[renderer_type]:
            renderer.update(items)


async def render_as_sse_items(
    app: FastAPI,
    *,
    renderer_type: type[AbstractSSERenderer],
    messages_check_interval: NonNegativeFloat = 3,
) -> AsyncIterable[str]:
    """used by the sse endpoint to render the content as it changes"""

    manager = RendererManager.get_from_app_state(app)
    renderer = renderer_type()
    manager.register_renderer(renderer)

    update_id, messages = renderer.get_messages()

    # Avoid the browser reconnecting
    while True:
        if renderer.changes_detected(last_update_id=update_id):
            yield f"data: {FastUI(root=messages).model_dump_json(by_alias=True, exclude_none=True)}\n\n"

        await asyncio.sleep(messages_check_interval)
        update_id, messages = renderer.get_messages()


def setup_sse(app: FastAPI) -> None:
    async def on_startup() -> None:
        renderer_manager = RendererManager()
        renderer_manager.set_to_app_state(app)

    app.add_event_handler("startup", on_startup)
