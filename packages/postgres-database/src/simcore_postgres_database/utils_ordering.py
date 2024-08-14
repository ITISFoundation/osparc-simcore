from enum import Enum
from typing import TypedDict


class OrderDirection(str, Enum):
    ASC = "asc"
    DESC = "desc"


class OrderByDict(TypedDict):
    field: str
    direction: OrderDirection


# Example usage
order_by_example: OrderByDict = {
    "field": "example_field",
    "direction": OrderDirection.ASC,
}
