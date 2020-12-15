"""
    Data models
"""

from datetime import datetime
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field, HttpUrl, constr

GITHUB_URL = "https://github.com/"

ItemsSequence = Union[str, List]


def comma_separated_to_list(values: ItemsSequence) -> List:
    return [v.strip() for v in values.split(",")] if isinstance(values, str) else values


TreePath = constr(regex=r"[\w:]+")  # Examples a::b::c


class Classifier(BaseModel):
    classifier: str = Field(
        ..., description="Unique identifier used to tag studies or services", example=""
    )
    display_name: str
    short_description: Optional[str]
    url: Optional[HttpUrl] = Field(
        None,
        description="Link to more information",
        example="https://scicrunch.org/resources/Any/search?q=osparc&l=osparc",
    )


class DataBundleFile(BaseModel):
    # meta
    build_date: datetime = datetime.now()
    vcs_url: Optional[str]
    vcs_ref: Optional[str]

    # data
    classifiers: Dict[TreePath, Classifier]
