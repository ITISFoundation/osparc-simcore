from typing import TypeAlias

from pydantic import BaseModel

ProgressUnit: TypeAlias = str


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
