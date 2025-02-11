from pathlib import Path

from pydantic import BaseModel, model_validator


class ZipTaskStart(BaseModel):
    paths: list[Path]

    @model_validator(mode="after")
    def _check_paths(self, value):
        if not value:
            raise ValueError("Empty paths error")
        return value
