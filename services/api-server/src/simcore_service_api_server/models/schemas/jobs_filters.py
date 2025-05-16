from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from pydantic.config import JsonDict


class MetadataFilterItem(BaseModel):
    name: Annotated[
        str,
        StringConstraints(min_length=1, max_length=255),
        Field(description="Name fo the metadata field"),
    ]
    pattern: Annotated[
        str,
        StringConstraints(min_length=1, max_length=255),
        Field(description="Exact value or glob pattern"),
    ]


class JobMetadataFilter(BaseModel):
    any: Annotated[
        list[MetadataFilterItem],
        Field(description="Matches any custom metadata field (OR logic)"),
    ]
    # NOTE: AND logic shall be implemented as `all: list[MetadataFilterItem] | None = None`

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
