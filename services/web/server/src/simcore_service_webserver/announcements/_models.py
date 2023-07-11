from datetime import datetime
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, Field


class Announcement(BaseModel):
    id_: str = Field(..., alias="id")
    products: list[Literal["osparc", "s4l", "s4llite", "tis"]]
    start: datetime
    end: datetime
    title: str
    description: str
    link: str
    widgets: list[Literal["login", "ribbon", "user-menu"]]

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
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
