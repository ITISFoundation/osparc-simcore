from typing import Any, Dict, Union

AnyDict = Dict[str, Any]
ListAnyDict = list[AnyDict]

# Represent the type returned by e.g. json.load
JSON = Union[AnyDict, ListAnyDict]
