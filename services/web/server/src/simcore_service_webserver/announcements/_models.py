from datetime import datetime
from typing import Literal

import arrow
from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator


# NOTE: this model is used for BOTH
# - parse+validate from redis
# - schema in the response
class Announcement(BaseModel):
    id: str
    products: list[str]
    start: datetime
    end: datetime
    title: str
    description: str
    link: str
    widgets: list[Literal["login", "ribbon", "user-menu"]]

    @field_validator("end")
    @classmethod
    def _check_start_before_end(cls, v, info: ValidationInfo):
        if start := info.data.get("start"):
            end = v
            if end <= start:
                msg = f"end={end!r} is not before start={start!r}"
                raise ValueError(msg)
        return v

    def expired(self) -> bool:
        return self.end <= arrow.utcnow().datetime

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": "Student_Competition_2023",
                    "products": ["s4llite"],
                    "start": "2023-06-22T15:00:00.000Z",
                    "end": "2023-11-01T02:00:00.000Z",
                    "title": "Student Competition 2023",
                    "description": "For more information click <a href='https://zmt.swiss/news-and-events/news/sim4life/s4llite-student-competition-2023/' style='color: white' target='_blank'>here</a>",
                    "link": "https://zmt.swiss/news-and-events/news/sim4life/s4llite-student-competition-2023/",
                    "widgets": ["login", "ribbon"],
                },
                {
                    "id": "TIP_v2",
                    "products": ["tis"],
                    "start": "2023-07-22T15:00:00.000Z",
                    "end": "2023-08-01T02:00:00.000Z",
                    "title": "TIP v2",
                    "description": "For more information click <a href='https://itis.swiss/tools-and-systems/ti-planning/' style='color: white' target='_blank'>here</a>",
                    "link": "https://itis.swiss/tools-and-systems/ti-planning/",
                    "widgets": ["login", "ribbon", "user-menu"],
                },
            ]
        }
    )
