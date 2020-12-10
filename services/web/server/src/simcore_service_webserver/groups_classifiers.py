"""
    Data models
"""
import os
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field, HttpUrl, constr, validator

GITHUB_URL = "https://github.com/"

ItemsSequence = Union[str, List]


def comma_separated_to_list(values: ItemsSequence) -> List:
    return [v.strip() for v in values.split(",")] if isinstance(values, str) else values


ClassifierName = constr(regex=r"[\w:]+")


class Classifier(BaseModel):
    classifier: str
    display_name: str
    short_description: Optional[str]
    logo: Optional[Path] = None
    aliases: ItemsSequence = []
    created_by: str
    released: Optional[date] = None
    related: ItemsSequence = []
    url: Optional[HttpUrl] = None
    github_url: Optional[HttpUrl] = None
    wikipedia_url: Optional[HttpUrl] = None
    markdown: Optional[str] = ""
    rrid: Optional[str] = ""

    @validator("github_url")
    @classmethod
    def check_github_domain(cls, v):
        if v.startswith("gh:"):
            return v.replace("gh:", GITHUB_URL)
        if not v.startswith(GITHUB_URL):
            raise ValueError("expected github url or gh: prefix")

    _normalize_related = validator("related", allow_reuse=True)(comma_separated_to_list)
    _normalize_alias = validator("aliases", allow_reuse=True)(comma_separated_to_list)


class Collection(BaseModel):
    items: List[str] = Field(
        ..., description="List of studies repos associated to this collection"
    )
    display_name: str
    created_by: str
    markdown: Optional[str] = ""


class DataBundleFile(BaseModel):
    # meta
    build_date: str = os.environ.get("BUILD_DATE", str(datetime.now()))
    vcs_url: Optional[str] = os.environ.get("VCS_URL")
    vcs_ref: Optional[str] = os.environ.get("VCS_REF")

    # data
    classifiers: Dict[ClassifierName, Classifier]
    collections: Dict[str, Collection] = {}
