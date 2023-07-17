from typing import Any, TypeAlias

AnyDict: TypeAlias = dict[str, Any]
ListAnyDict: TypeAlias = list[AnyDict]

# Represent the type returned by e.g. json.load
JSON: TypeAlias = AnyDict | ListAnyDict
