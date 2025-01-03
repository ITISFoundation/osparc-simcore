from typing_extensions import TypedDict


class AccessRightsDict(TypedDict):
    read: bool
    write: bool
    delete: bool
