from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from pydantic.config import JsonDict


class MetadataFilterItem(BaseModel):
    name: Annotated[
        str,
        StringConstraints(min_length=1, max_length=255),
        Field(description="Name of the metadata field"),
    ]
    pattern: Annotated[
        str,
        StringConstraints(min_length=1, max_length=255),
        Field(description="Exact value or glob pattern"),
    ]


class JobMetadataFilter(BaseModel):
    any: Annotated[
        list[MetadataFilterItem] | None,
        Field(description="Matches any custom metadata field (OR logic)"),
    ] = None
    all: Annotated[
        list[MetadataFilterItem] | None,
        Field(description="Matches all custom metadata fields (AND logic)"),
    ] = None

    @model_validator(mode="after")
    def _check_any_and_all_are_mutually_exclusive(self) -> "JobMetadataFilter":
        if self.any and self.all:
            msg = "metadata.any and metadata.all are mutually exclusive"
            raise ValueError(msg)
        if not self.any and not self.all:
            msg = "Either metadata.any or metadata.all must be provided"
            raise ValueError(msg)
        return self

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
                "examples": [
                    {
                        "any": [
                            {
                                "name": "solver_type",
                                "pattern": "FEM",
                            },
                            {
                                "name": "mesh_cells",
                                "pattern": "1*",
                            },
                        ]
                    },
                    {
                        "any": [
                            {
                                "name": "solver_type",
                                "pattern": "*CFD*",
                            }
                        ]
                    },
                ]
            }
        )

    model_config = ConfigDict(
        json_schema_extra=_update_json_schema_extra,
    )
