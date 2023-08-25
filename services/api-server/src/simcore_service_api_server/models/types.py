from typing import Any, TypeAlias

AnyDict: TypeAlias = dict[str, Any]
ListAnyDict: TypeAlias = list[AnyDict]

# Represent the type returned by e.g. json.load
AnyJson: TypeAlias = AnyDict | ListAnyDict
