from typing import Any, Dict, List, Union

AnyDict = Dict[str, Any]
ListAnyDict = List[AnyDict]

# Represent the type returned by e.g. json.load
JSON = Union[AnyDict, ListAnyDict]
