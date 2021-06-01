from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator

ComposeSpecModel = Optional[Dict[str, Any]]


class PathsMappingModel(BaseModel):
    inputs_path: Path = Field(
        ..., description="path where the service expects all the inputs folder"
    )
    outputs_path: Path = Field(
        ..., description="path where the service expects all the outputs folder"
    )
    other_paths: List[Path] = Field(
        [],
        description="optional list of path which contents need to be saved and restored",
    )

    @validator("other_paths", always=True)
    @classmethod
    def convert_none_to_empty_list(cls, v):
        return [] if v is None else v
