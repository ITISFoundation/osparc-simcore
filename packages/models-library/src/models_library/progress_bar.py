from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class ProgressReport:
    actual_value: float
    total: float

    @property
    def percent_value(self) -> float:
        if self.total != 0:
            return max(min(self.actual_value / self.total, 1.0), 0.0)
        return 0
