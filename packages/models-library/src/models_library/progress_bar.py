from typing import Any, ClassVar, Literal, TypeAlias

from pydantic import BaseModel

# NOTE: keep a list of possible unit, and please use correct official unit names
ProgressUnit: TypeAlias = Literal["Byte"]


class StructuredMessage(BaseModel):
    description: str
    current: float
    total: int
    unit: str | None
    sub: "StructuredMessage | None"


class ProgressReport(BaseModel):
    actual_value: float
    total: float
    unit: ProgressUnit | None = None
    message: StructuredMessage | None = None

    @property
    def percent_value(self) -> float:
        if self.total != 0:
            return max(min(self.actual_value / self.total, 1.0), 0.0)
        return 0

    def _recursive_compose_message(self, struct_msg: StructuredMessage) -> str:
        msg = f"{struct_msg.description}"
        if struct_msg.sub:
            return f"{msg}/{self._recursive_compose_message(struct_msg.sub)}"
        msg = f"{msg} {struct_msg.current} / {struct_msg.total}"
        return f"{msg} {struct_msg.unit}" if struct_msg.unit else f"{msg} %"

    @property
    def composed_message(self) -> str:
        msg = f"{self.actual_value} / {self.total}"
        msg = f"{msg} {self.unit}" if self.unit else f"{msg} %"
        if self.message:
            msg = f"{self.message.description} ({msg})"
            if self.message.sub:
                msg = f"{msg}/{self._recursive_compose_message(self.message.sub)}"

        return msg

    class Config:
        frozen = True
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                # typical percent progress (no units)
                {
                    "actual_value": 0.3,
                    "total": 1.0,
                    "message": "downloading 0.3/1.0",
                },
                # typical byte progress
                {
                    "actual_value": 128.5,
                    "total": 1024.0,
                    "unit": "Byte",
                    "message": "downloading 128.5/1024.0 Byte",
                },
            ]
        }
