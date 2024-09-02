from typing import TypeAlias

from pydantic import ConstrainedFloat

TaskId = str

ProgressMessage: TypeAlias = str


class ProgressPercent(ConstrainedFloat):
    ge = 0.0
    le = 1.0
