import json
from collections.abc import Callable
from typing import Any, Final, NamedTuple

import orjson
from pydantic.json import pydantic_encoder


class SeparatorTuple(NamedTuple):
    item_separator: str
    key_separator: str


class OrJsonAdapter:
    """
    Adapts orjson to have the same interface as json.dumps and json.loads

    NOTE orjson performs better than json. SEE https://github.com/ijl/orjson?tab=readme-ov-file#performance
    """

    # orjson always use (",". ":") as separators
    _default_separator: Final = SeparatorTuple(item_separator=",", key_separator=":")

    @classmethod
    def dumps(
        cls,
        obj,
        *,
        default: Callable[[Any], Any] | None = None,
        indent: int | None = None,
        separators: SeparatorTuple | tuple[str, str] | None = None,
        sort_keys: bool = False,
    ) -> str:
        options = orjson.OPT_INDENT_2 if indent is not None else 0
        if sort_keys:
            options |= orjson.OPT_SORT_KEYS

        # SEE https://github.com/ijl/orjson
        # - orjson.dumps returns *bytes*, to match standard json.dumps we need to decode
        result: str = orjson.dumps(obj, default=default, option=options).decode("utf-8")

        if separators is not None:
            sep = SeparatorTuple(*separators)
            if sep != cls._default_separator:
                result = result.replace(":", sep.key_separator).replace(
                    ",", sep.item_separator
                )

        return result

    loads = orjson.loads


def json_dumps(obj: Any, **json_dumps_kwargs):
    """Keeps json.dump interface with different defaults"""

    json_dumps_kwargs.setdefault("default", pydantic_encoder)  # rich encoder
    if "indent" not in json_dumps_kwargs:
        json_dumps_kwargs.setdefault(
            "separators",
            SeparatorTuple(item_separator=",", key_separator=":"),  # compact separators
        )
    return json.dumps(obj, **json_dumps_kwargs)


def orjson_dumps(obj: Any, **orjson_kwargs):
    orjson_kwargs.setdefault(
        "default", pydantic_encoder
    )  # TODO: remove and see customize only where needed
    result: str = orjson.dumps(obj, **orjson_kwargs).decode("utf-8")
    return result
