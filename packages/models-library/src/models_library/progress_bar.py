from typing import Any, ClassVar, Literal, TypeAlias

from pydantic import BaseModel

# NOTE: keep a list of possible unit, and please use correct official unit names
ProgressUnit: TypeAlias = Literal["Byte"]


class ProgressReport(BaseModel):
    actual_value: float
    total: float
    unit: ProgressUnit | None = None

    @property
    def percent_value(self) -> float:
        if self.total != 0:
            return max(min(self.actual_value / self.total, 1.0), 0.0)
        return 0

    class Config:
        frozen = True
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                # typical percent progress (no units)
                {
                    "actual_value": 0.3,
                    "total": 1.0,
                },
                # typical byte progress
                {
                    "actual_value": 128.5,
                    "total": 1024.0,
                    "unit": "Byte",
                },
            ]
        }
