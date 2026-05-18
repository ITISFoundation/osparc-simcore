import textwrap
from typing import Annotated

from fastapi import HTTPException, Query, status
from pydantic import ValidationError

from ...models.schemas.jobs_filters import JobMetadataFilter, MetadataFilterItem


def _parse_metadata_items(raw: list[str]) -> list[MetadataFilterItem]:
    items = []
    for item in raw:
        if ":" not in item:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid metadata filter format: '{item}'. Expected 'key:pattern'.",
            )
        name, pattern = item.split(":", 1)
        items.append(MetadataFilterItem(name=name, pattern=pattern))
    return items


def get_job_metadata_filter(
    any_: Annotated[
        list[str] | None,
        Query(
            alias="metadata.any",
            description=textwrap.dedent(
                """
            Filters jobs based on **any** of the matches on custom metadata fields.

            *Format*: `key:pattern` where pattern can contain glob wildcards
            """
            ),
            examples=[
                ["key1:val*", "key2:exactval"],
            ],
        ),
    ] = None,
    all_: Annotated[
        list[str] | None,
        Query(
            alias="metadata.all",
            description=textwrap.dedent(
                """
            Filters jobs based on **all** of the matches on custom metadata fields.

            *Format*: `key:pattern` where pattern can contain glob wildcards
            """
            ),
            examples=[
                ["solver_type:FEM", "mesh_cells:1*"],
            ],
        ),
    ] = None,
) -> JobMetadataFilter | None:
    if not any_ and not all_:
        return None

    try:
        return JobMetadataFilter(
            any=_parse_metadata_items(any_) if any_ else None,
            all=_parse_metadata_items(all_) if all_ else None,
        )
    except ValidationError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=err.errors(include_context=False),
        ) from err
