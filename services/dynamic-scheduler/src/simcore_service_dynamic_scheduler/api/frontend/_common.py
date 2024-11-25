from collections.abc import Iterator
from contextlib import contextmanager

from nicegui import ui


@contextmanager
def base_page(*, title: str | None = None) -> Iterator[None]:
    display_title = (
        "Dynamic Scheduler" if title is None else f"Dynamic Scheduler - {title}"
    )
    ui.page_title(display_title)

    with ui.header(elevated=True).classes("items-center"):
        ui.button(icon="o_home", on_click=lambda: ui.navigate.to("/"))
        ui.label(display_title)

    yield None
