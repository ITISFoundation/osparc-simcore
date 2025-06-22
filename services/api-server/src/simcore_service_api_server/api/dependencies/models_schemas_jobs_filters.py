import textwrap
from typing import Annotated

from fastapi import Query

from ...models.schemas.jobs_filters import JobMetadataFilter, MetadataFilterItem


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
) -> JobMetadataFilter | None:
    """
    Example input:

        /solvers/-/releases/-/jobs?metadata.any=key1:val*&metadata.any=key2:exactval

    This will be converted to:
        JobMetadataFilter(
            any=[
                MetadataFilterItem(name="key1", pattern="val*"),
                MetadataFilterItem(name="key2", pattern="exactval"),
            ]
        )

    This is used to filter jobs based on custom metadata fields.

    """
    if not any_:
        return None

    items = []
    for item in any_:
        try:
            name, pattern = item.split(":", 1)
        except ValueError:
            continue  # or raise HTTPException
        items.append(MetadataFilterItem(name=name, pattern=pattern))
    return JobMetadataFilter(any=items)
