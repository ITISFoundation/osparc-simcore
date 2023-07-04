import re
import urllib.parse
from typing import Any

from pydantic import BaseModel, Field
from pydantic.types import ConstrainedStr

# RESOURCE NAMES https://cloud.google.com/apis/design/resource_names
#
#
# API Service Name          Collection ID   Resource ID         Collection ID  Resource ID
# //storage.googleapis.com  /buckets        /bucket-id          /objects       /object-id
# //mail.googleapis.com     /users          /name@example.com   /settings      /customFrom
#
#
# - Relative Resource Name:
#    A URI path (path-noscheme) without the leading "/". It identifies a resource within the API service.
#     "shelves/shelf1/books/book2"
#
# - Resource Name vs URL
#   This is a calendar event resource name.
#    "//calendar.googleapis.com/users/john smith/events/123"
#
#   This is the corresponding HTTP URL.
#
# SEE https://tools.ietf.org/html/rfc3986#appendix-B
#


_RELATIVE_RESOURCE_NAME_RE = r"^([^\s/]+/?){1,10}$"


class RelativeResourceName(ConstrainedStr):
    regex = re.compile(_RELATIVE_RESOURCE_NAME_RE)

    class Config:
        frozen = True


# NOTE: we quote parts in a single resource_name and unquote when split


def parse_last_resource_id(resource_name: RelativeResourceName) -> str:
    match = RelativeResourceName.regex.match(resource_name)
    last_quoted_part = match.group(1)
    return urllib.parse.unquote_plus(last_quoted_part)


def compose_resource_name(*collection_or_resource_ids) -> RelativeResourceName:
    quoted_parts = [
        urllib.parse.quote_plus(f"{_id}".lstrip("/"))
        for _id in collection_or_resource_ids
    ]
    return RelativeResourceName("/".join(quoted_parts))


def split_resource_name(resource_name: RelativeResourceName) -> list[str]:
    quoted_parts = resource_name.split("/")
    return [f"{urllib.parse.unquote_plus(p)}" for p in quoted_parts]


#
# For resource definitions, the first field should be a string field for the resource name,
# and it should be called *name*
# Resource IDs must be clearly documented whether they are assigned by the client, the server, or either
#
class BaseResource(BaseModel):
    name: RelativeResourceName = Field(None, example="solvers/isolve/releases/1.2.3")
    id: Any = Field(None, description="Resource ID", example="1.2.3")  # noqa: A003


class BaseCollection(BaseModel):
    name: RelativeResourceName = Field(None, example="solvers/isolve/releases")
    id: Any = Field(None, description="Collection ID", example="releases")  # noqa: A003
