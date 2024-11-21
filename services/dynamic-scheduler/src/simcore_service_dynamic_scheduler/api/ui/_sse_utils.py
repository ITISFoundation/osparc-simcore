import asyncio
import json
from abc import ABC, abstractmethod
from collections.abc import AsyncIterable
from typing import Any, TypeAlias
from weakref import WeakSet

from fastapi import FastAPI
from fastui import AnyComponent, FastUI
from pydantic import NonNegativeFloat
from servicelib.fastapi.app_state import SingletonInAppStateMixin

UpdateID: TypeAlias = int


class AbstractSSERenderer(ABC):
    def __init__(self, app: FastAPI) -> None:
        self.app = app
        self._items: list[Any] = []
        self._hash = self._get_items_hash()

    async def __aenter__(self):
        await RendererManager.get_from_app_state(self.app).register_renderer(self)
        return self

    async def __aexit__(self, *args):
        await RendererManager.get_from_app_state(self.app).unregister_renderer(
            type(self), self
        )

    def _get_items_hash(self) -> int:
        return hash(json.dumps(self._items))

    def update(self, items: list[Any]) -> None:
        self._items = items
        self._hash = self._get_items_hash()

    def _get_update_id(self) -> UpdateID:
        return self._hash

    def changes_detected(self, last_update_id: UpdateID) -> bool:
        return last_update_id != self._get_update_id()

    @staticmethod
    @abstractmethod
    def render_item(item: Any) -> AnyComponent:
        """returns a `fastui.component` to which renders the content of the item"""

    def get_messages(self) -> tuple[UpdateID, list[AnyComponent]]:
        return self._get_update_id(), [self.render_item(x) for x in self._items]


class RendererManager(SingletonInAppStateMixin):
    app_state_name: str = "renderer_manager"
    """Allows to register SSE renderers and distribute data based on type"""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._renderers: dict[
            type[AbstractSSERenderer], WeakSet[AbstractSSERenderer]
        ] = {}

    async def register_renderer(self, renderer: AbstractSSERenderer) -> None:
        renderer_type = type(renderer)

        if renderer_type not in self._renderers:
            self._renderers[renderer_type] = WeakSet()

        async with self._lock:
            self._renderers[renderer_type].add(renderer)

    async def unregister_renderer(
        self, renderer_type: type[AbstractSSERenderer], renderer: AbstractSSERenderer
    ) -> None:
        if renderer_type not in self._renderers:
            pass
        async with self._lock:
            self._renderers[renderer_type].remove(renderer)

    async def update_renderers(
        self, renderer_type: type[AbstractSSERenderer], items: list[Any]
    ) -> None:
        """propagate updates to all instances of said type SSERenderer"""
        if renderer_type not in self._renderers:
            return

        async with self._lock:
            for renderer in self._renderers[renderer_type]:
                renderer.update(items)


async def render_items_on_change(
    app: FastAPI,
    *,
    renderer_type: type[AbstractSSERenderer],
    check_interval: NonNegativeFloat = 1,
) -> AsyncIterable[str]:
    """Used by an SSE endpoint to provide updates for a specific renderer.
    Only sends out new updates if the underlying dataset canged.

    Arguments:
        renderer_type -- the class rendering an item to be displayed, must be defined by the user

    Keyword Arguments:
        check_interval -- interval at which to check for new updates (default: {1})
    """

    async with renderer_type(app) as renderer:
        last_update_id, messages = renderer.get_messages()

        # render current state
        yield f"data: {FastUI(root=messages).model_dump_json(by_alias=True, exclude_none=True)}\n\n"

        # Avoid the browser reconnecting
        while True:
            await asyncio.sleep(check_interval)

            update_id, messages = renderer.get_messages()

            if renderer.changes_detected(last_update_id=last_update_id):
                yield f"data: {FastUI(root=messages).model_dump_json(by_alias=True, exclude_none=True)}\n\n"

            last_update_id = update_id


async def update_items(
    app: FastAPI, *, renderer_type: type[AbstractSSERenderer], items: list[Any]
) -> None:
    await RendererManager.get_from_app_state(app).update_renderers(renderer_type, items)


def setup_sse(app: FastAPI) -> None:
    async def on_startup() -> None:
        renderer_manager = RendererManager()
        renderer_manager.set_to_app_state(app)

    app.add_event_handler("startup", on_startup)
