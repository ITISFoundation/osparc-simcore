from collections.abc import Iterator
from contextlib import contextmanager

from nicegui import ui


@contextmanager
def base_page(*, title: str | None = None, colour: str = "#D3D3D3") -> Iterator[None]:
    display_title = (
        "Dynamic Scheduler" if title is None else f"Dynamic Scheduler - {title}"
    )
    ui.page_title(display_title)
    with ui.header(elevated=True).style(f"background-color: {colour}").classes(
        "items-center justify-between"
    ):
        ui.label("HEADER")

    yield None

    with ui.footer().style(f"background-color: {colour}"):
        ui.label("FOOTER")
