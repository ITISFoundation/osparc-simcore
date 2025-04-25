import re
import urllib.parse
from typing import Annotated, TypeAlias

from pydantic import Field, TypeAdapter
from pydantic.types import StringConstraints

# RESOURCE NAMES https://google.aip.dev/122
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


RelativeResourceName: TypeAlias = Annotated[
    str, StringConstraints(pattern=_RELATIVE_RESOURCE_NAME_RE), Field(frozen=True)
]

# NOTE: we quote parts in a single resource_name and unquote when split


def parse_last_resource_id(resource_name: RelativeResourceName) -> str:
    if match := re.match(_RELATIVE_RESOURCE_NAME_RE, resource_name):
        last_quoted_part = match.group(1)
        return urllib.parse.unquote_plus(last_quoted_part)
    msg = f"Invalid '{resource_name=}' does not match RelativeResourceName"
    raise ValueError(msg)


def compose_resource_name(*collection_or_resource_ids) -> RelativeResourceName:
    quoted_parts = [
        urllib.parse.quote_plus(f"{_id}".lstrip("/"))
        for _id in collection_or_resource_ids
    ]
    return TypeAdapter(RelativeResourceName).validate_python("/".join(quoted_parts))


def split_resource_name(resource_name: RelativeResourceName) -> list[str]:
    quoted_parts = resource_name.split("/")
    return [f"{urllib.parse.unquote_plus(p)}" for p in quoted_parts]


def parse_collections_ids(resource_name: RelativeResourceName) -> list[str]:
    """
    Example:
        resource_name = "solvers/simcore%2Fservices%2Fcomp%2Fisolve/releases/1.3.4/jobs/f622946d-fd29-35b9-a193-abdd1095167c/outputs/output+22"
        returns ["solvers", "releases", "jobs", "outputs"]
    """
    parts = split_resource_name(resource_name)
    return parts[::2]


def parse_resources_ids(resource_name: RelativeResourceName) -> list[str]:
    """
    Example:
        resource_name = "solvers/simcore%2Fservices%2Fcomp%2Fisolve/releases/1.3.4/jobs/f622946d-fd29-35b9-a193-abdd1095167c/outputs/output+22"
        returns ["simcore/services/comp/isolve", "1.3.4", "f622946d-fd29-35b9-a193-abdd1095167c", "output 22"]
    """
    parts = split_resource_name(resource_name)
    return parts[1::2]


def split_resource_name_as_dict(
    resource_name: RelativeResourceName,
) -> dict[str, str | None]:
    """
    Returns a map such as resource_ids[Collection-ID] == Resource-ID
    """
    parts = split_resource_name(resource_name)
    return dict(zip(parts[::2], parts[1::2], strict=False))
