from typing import TypedDict


class AccessRightsDict(TypedDict):
    read: bool
    write: bool
    delete: bool
