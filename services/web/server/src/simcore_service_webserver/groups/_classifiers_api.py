"""
    - Every group has a set of "official" classifiers and its users tag studies with them
    - Classifiers can be defined in two ways:
        1. a static bundle that is stored in group_classifiers.c.bundle
        2. using research resources from scicrunch.org (see group_classifiers.c.uses_scicrunch )
    - The API Classifiers model returned in
        1. is the bundle
        2. a dynamic tree built from validated RRIDs (in ResearchResourceRepository)
"""

import logging
from typing import Annotated, Any, Final, Literal, TypeAlias

import sqlalchemy as sa
from aiohttp import web
from aiopg.sa.result import RowProxy
from pydantic import (
    BaseModel,
    Field,
    HttpUrl,
    StringConstraints,
    TypeAdapter,
    ValidationError,
    field_validator,
)
from simcore_postgres_database.models.classifiers import group_classifiers

from ..db.plugin import get_database_engine
from ..scicrunch.db import ResearchResourceRepository
from ..scicrunch.service_client import SciCrunch

_logger = logging.getLogger(__name__)
MAX_SIZE_SHORT_MSG: Final[int] = 100


# DOMAIN MODELS ---


TreePath: TypeAlias = Annotated[
    # Examples 'a::b::c
    str,
    StringConstraints(pattern=r"[\w:]+"),
]


class ClassifierItem(BaseModel):
    classifier: str = Field(
        ..., description="Unique identifier used to tag studies or services"
    )
    display_name: str
    short_description: str | None
    url: HttpUrl | None = Field(
        None,
        description="Link to more information",
        examples=["https://scicrunch.org/resources/Any/search?q=osparc&l=osparc"],
    )

    @field_validator("short_description", mode="before")
    @classmethod
    def truncate_to_short(cls, v):
        if v and len(v) >= MAX_SIZE_SHORT_MSG:
            return v[:MAX_SIZE_SHORT_MSG] + "…"
        return v


class Classifiers(BaseModel):
    # meta
    vcs_url: str | None
    vcs_ref: str | None

    # data
    classifiers: dict[TreePath, ClassifierItem]


# DATABASE --------


class GroupClassifierRepository:
    def __init__(self, app: web.Application):
        self.engine = get_database_engine(app)

    async def _get_bundle(self, gid: int) -> RowProxy | None:
        async with self.engine.acquire() as conn:
            bundle: RowProxy | None = await conn.scalar(
                sa.select(group_classifiers.c.bundle).where(
                    group_classifiers.c.gid == gid
                )
            )
            return bundle

    async def get_classifiers_from_bundle(self, gid: int) -> dict[str, Any]:
        bundle = await self._get_bundle(gid)
        if bundle:
            try:
                # truncate bundle to what is needed and drop the rest
                return Classifiers(**bundle).model_dump(
                    exclude_unset=True, exclude_none=True
                )
            except ValidationError as err:
                _logger.error(
                    "DB corrupt data in 'groups_classifiers' table. "
                    "Invalid classifier for gid=%d: %s. "
                    "Returning empty bundle.",
                    gid,
                    err,
                )
        return {}

    async def group_uses_scicrunch(self, gid: int) -> bool:
        async with self.engine.acquire() as conn:
            value: RowProxy | None = await conn.scalar(
                sa.select(group_classifiers.c.uses_scicrunch).where(
                    group_classifiers.c.gid == gid
                )
            )
            return bool(value)


# HELPERS FOR API HANDLERS --------------


async def build_rrids_tree_view(
    app: web.Application, tree_view_mode: Literal["std"] = "std"
) -> dict[str, Any]:
    if tree_view_mode != "std":
        raise web.HTTPNotImplemented(
            reason="Currently only 'std' option for the classifiers tree view is implemented"
        )

    scicrunch = SciCrunch.get_instance(app)
    repo = ResearchResourceRepository(app)

    flat_tree_view: dict[TreePath, ClassifierItem] = {}
    for resource in await repo.list_resources():
        try:
            validated_item = ClassifierItem(
                classifier=resource.rrid,
                display_name=resource.name.title(),
                short_description=resource.description,
                url=scicrunch.get_resolver_web_url(resource.rrid),
            )

            node = TypeAdapter(TreePath).validate_python(
                validated_item.display_name.replace(":", " ")
            )
            flat_tree_view[node] = validated_item

        except ValidationError as err:
            _logger.warning(
                "Cannot convert RRID into a classifier item. Skipping. Details: %s", err
            )

    return Classifiers.model_construct(classifiers=flat_tree_view).model_dump(
        exclude_unset=True
    )
