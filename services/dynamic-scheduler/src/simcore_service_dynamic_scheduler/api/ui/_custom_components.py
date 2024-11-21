from typing import Any

from fastui import AnyComponent
from fastui import components as c


def markdown_list_display(data: list[tuple[Any, Any]]) -> AnyComponent:
    return c.Markdown(text="\n".join(f"- **{key:}** `{value}`" for key, value in data))
