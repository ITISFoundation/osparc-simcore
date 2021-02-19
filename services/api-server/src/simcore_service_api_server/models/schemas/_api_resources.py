import urllib.parse
from typing import Any, List

from pydantic import BaseModel, Field, constr

# TODO: this is just a concept/idea based on https://cloud.google.com/apis/design/resource_names

RESOURCE_NAME_RE = r"^(/?[^\s/]+)+$"
ResourceName = constr(regex=RESOURCE_NAME_RE)


def compose_resource_name(*resource_ids) -> ResourceName:
    quoted_parts = [urllib.parse.quote_plus(_id.strip("/")) for _id in resource_ids]
    return ResourceName("/" + "/".join(quoted_parts))


def split_resource_name(resource_name: ResourceName) -> List[str]:
    quoted_parts = resource_name.strip("/").split("/")
    return [f"/{urllib.parse.unquote_plus(p)}" for p in quoted_parts]


def parse_resource_id(resource_name: ResourceName) -> str:
    match = ResourceName.regex.match(resource_name)
    last_quoted_part = match.group(1)
    return urllib.parse.unquote_plus(last_quoted_part)


class BaseResource(BaseModel):
    name: str = Field(None, example="/solvers/isolve/releases/1.2.3")
    # While full resource names resemble normal URLs, they are not the same thing

    id: Any = Field(None, description="Resource ID", example="/1.2.3")
    # Resource IDs must be clearly documented whether they are assigned by the client, the server, or either


class BaseCollection(BaseModel):
    name: str = Field(None, example="solvers/isolve/releases")
    id: Any = Field(None, description="Collection ID", example="/releases")
