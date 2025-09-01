from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict
from pydantic.config import JsonDict

# NOTE: keep a list of possible unit, and please use correct official unit names
ProgressUnit: TypeAlias = Literal["Byte"]


class ProgressStructuredMessage(BaseModel):
    description: str
    current: float
    total: int
    unit: str | None = None
    sub: "ProgressStructuredMessage | None" = None

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
                "examples": [
                    {
                        "description": "some description",
                        "current": 12.2,
                        "total": 123,
                    },
                    {
                        "description": "some description",
                        "current": 12.2,
                        "total": 123,
                        "unit": "Byte",
                    },
                    {
                        "description": "downloading",
                        "current": 2.0,
                        "total": 5,
                        "sub": {
                            "description": "port 2",
                            "current": 12.2,
                            "total": 123,
                            "unit": "Byte",
                        },
                    },
                ]
            }
        )

    model_config = ConfigDict(json_schema_extra=_update_json_schema_extra)


UNITLESS = None


class ProgressReport(BaseModel):
    actual_value: float
    total: float = 1.0
    attempt: int = 0
    unit: ProgressUnit | None = UNITLESS
    message: ProgressStructuredMessage | None = None

    @property
    def percent_value(self) -> float:
        if self.total != 0:
            return max(min(self.actual_value / self.total, 1.0), 0.0)
        return 0

    def _recursive_compose_message(self, struct_msg: ProgressStructuredMessage) -> str:
        msg = f"{struct_msg.description}"
        if struct_msg.sub:
            return f"{msg}/{self._recursive_compose_message(struct_msg.sub)}"
        msg = f"{msg} {struct_msg.current} / {struct_msg.total}"
        return f"{msg} {struct_msg.unit}" if struct_msg.unit is not UNITLESS else msg

    @property
    def composed_message(self) -> str:
        msg = f"{self.actual_value} / {self.total}"
        msg = f"{msg} {self.unit}" if self.unit is not UNITLESS else msg
        if self.message:
            msg = f"{self.message.description} ({msg})"
            if self.message.sub:
                msg = f"{msg}/{self._recursive_compose_message(self.message.sub)}"

        return msg

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
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
                # typical progress with sub progresses
                {
                    "actual_value": 0.3,
                    "total": 1.0,
                    "message": {
                        "description": "downloading",
                        "current": 2.0,
                        "total": 5,
                        "sub": {
                            "description": "port 2",
                            "current": 12.2,
                            "total": 123,
                            "unit": "Byte",
                        },
                    },
                },
            ]
        },
    )
