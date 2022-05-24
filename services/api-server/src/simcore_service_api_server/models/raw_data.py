from typing import Any, Union

AnyDict = dict[str, Any]
ListAnyDict = list[AnyDict]

# Represent the type returned by e.g. json.load
JSON = Union[AnyDict, ListAnyDict]
