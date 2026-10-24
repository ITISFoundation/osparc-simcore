from typing import Any

type AnyDict = dict[str, Any]
type ListAnyDict = list[AnyDict]

# Represent the type returned by e.g. json.load
type AnyJson = AnyDict | ListAnyDict
