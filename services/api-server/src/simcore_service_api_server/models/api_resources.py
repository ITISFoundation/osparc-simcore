import re
import urllib.parse
from typing import Annotated, TypeAlias
from uuid import UUID

import parse  # type: ignore[import-untyped]
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, HttpUrl, TypeAdapter
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


def split_resource_name(resource_name: RelativeResourceName) -> tuple[str, ...]:
    """
    Example:
        resource_name = "solvers/simcore%2Fservices%2Fcomp%2Fisolve/releases/1.3.4/jobs/f622946d-fd29-35b9-a193-abdd1095167c/outputs/output+22"
        returns ("solvers", "simcore/services/comp/isolve", "releases", "1.3.4", "jobs", "f622946d-fd29-35b9-a193-abdd1095167c", "outputs", "output 22")
    """
    quoted_parts = resource_name.split("/")
    return tuple(f"{urllib.parse.unquote_plus(p)}" for p in quoted_parts)


def parse_collections_ids(resource_name: RelativeResourceName) -> tuple[str, ...]:
    """
    Example:
        resource_name = "solvers/simcore%2Fservices%2Fcomp%2Fisolve/releases/1.3.4/jobs/f622946d-fd29-35b9-a193-abdd1095167c/outputs/output+22"
        returns ("solvers", "releases", "jobs", "outputs")
    """
    parts = split_resource_name(resource_name)
    return parts[::2]


def parse_resources_ids(resource_name: RelativeResourceName) -> tuple[str, ...]:
    """
    Example:
        resource_name = "solvers/simcore%2Fservices%2Fcomp%2Fisolve/releases/1.3.4/jobs/f622946d-fd29-35b9-a193-abdd1095167c/outputs/output+22"
        returns ("simcore/services/comp/isolve", "1.3.4", "f622946d-fd29-35b9-a193-abdd1095167c", "output 22")
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


def _url_missing_only_job_id(url: str | None) -> str | None:
    if url is None:
        return None
    if set(parse.compile(url).named_fields) != {"job_id"}:
        raise ValueError(f"Missing job_id in {url=}")
    return url


class JobLinks(BaseModel):
    @staticmethod
    def _update_json_schema_extra(schema: dict) -> None:
        schema.update(
            {
                "examples": [
                    {
                        "url_template": "https://api.osparc.io/v0/jobs/{job_id}",
                        "runner_url_template": "https://runner.osparc.io/dashboard",
                        "outputs_url_template": "https://api.osparc.io/v0/jobs/{job_id}/outputs",
                    }
                ]
            }
        )

    model_config = ConfigDict(json_schema_extra=_update_json_schema_extra)

    url_template: Annotated[str | None, AfterValidator(_url_missing_only_job_id)]
    runner_url_template: str | None
    outputs_url_template: Annotated[
        str | None, AfterValidator(_url_missing_only_job_id)
    ]

    def url(self, job_id: UUID) -> HttpUrl | None:
        if self.url_template is None:
            return None
        return TypeAdapter(HttpUrl).validate_python(
            self.url_template.format(job_id=job_id)
        )

    def runner_url(self, job_id: UUID) -> HttpUrl | None:
        assert job_id  # nosec
        if self.runner_url_template is None:
            return None
        return TypeAdapter(HttpUrl).validate_python(self.runner_url_template)

    def outputs_url(self, job_id: UUID) -> HttpUrl | None:
        if self.outputs_url_template is None:
            return None
        return TypeAdapter(HttpUrl).validate_python(
            self.outputs_url_template.format(job_id=job_id)
        )
