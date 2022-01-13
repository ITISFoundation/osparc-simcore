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
from typing import Any, Dict, Optional

import sqlalchemy as sa
from aiohttp import web
from aiopg.sa.result import RowProxy
from pydantic import BaseModel, Field, HttpUrl, ValidationError, constr, validator
from simcore_postgres_database.models.classifiers import group_classifiers

from ._constants import APP_DB_ENGINE_KEY
from .scicrunch.db import ResearchResourceRepository
from .scicrunch.service_client import SciCrunch

logger = logging.getLogger(__name__)

# DOMAIN MODELS ---

TreePath = constr(regex=r"[\w:]+")  # Examples 'a::b::c
MAX_SIZE_SHORT_MSG = 100


class ClassifierItem(BaseModel):
    classifier: str = Field(
        ..., description="Unique identifier used to tag studies or services"
    )
    display_name: str
    short_description: Optional[str]
    url: Optional[HttpUrl] = Field(
        None,
        description="Link to more information",
        example="https://scicrunch.org/resources/Any/search?q=osparc&l=osparc",
    )

    @validator("short_description", pre=True)
    @classmethod
    def truncate_to_short(cls, v):
        if v and len(v) >= MAX_SIZE_SHORT_MSG:
            return v[:MAX_SIZE_SHORT_MSG] + "…"
        return v


class Classifiers(BaseModel):
    # meta
    vcs_url: Optional[str]
    vcs_ref: Optional[str]

    # data
    classifiers: Dict[TreePath, ClassifierItem]


# DATABASE --------


class GroupClassifierRepository:
    #
    # TODO: a repo: retrieves engine from app
    # TODO: a repo: some members acquire and retrieve connection
    # TODO: a repo: any validation error in a repo is due to corrupt data in db!

    def __init__(self, app: web.Application):
        self.engine = app[APP_DB_ENGINE_KEY]

    async def _get_bundle(self, gid: int) -> Optional[RowProxy]:
        async with self.engine.acquire() as conn:
            bundle: Optional[RowProxy] = await conn.scalar(
                sa.select([group_classifiers.c.bundle]).where(
                    group_classifiers.c.gid == gid
                )
            )
            return bundle

    async def get_classifiers_from_bundle(self, gid: int) -> Dict[str, Any]:
        bundle = await self._get_bundle(gid)
        if bundle:
            try:
                # truncate bundle to what is needed and drop the rest
                return Classifiers(**bundle).dict(exclude_unset=True, exclude_none=True)
            except ValidationError as err:
                logger.error(
                    "DB corrupt data in 'groups_classifiers' table. "
                    "Invalid classifier for gid=%d: %s. "
                    "Returning empty bundle.",
                    gid,
                    err,
                )
        return {}

    async def group_uses_scicrunch(self, gid: int) -> bool:
        async with self.engine.acquire() as conn:
            value: Optional[RowProxy] = await conn.scalar(
                sa.select([group_classifiers.c.uses_scicrunch]).where(
                    group_classifiers.c.gid == gid
                )
            )
            return bool(value)


# HELPERS FOR API HANDLERS --------------


async def build_rrids_tree_view(app, tree_view_mode="std") -> Dict[str, Any]:
    if tree_view_mode != "std":
        raise web.HTTPNotImplemented(
            reason="Currently only 'std' option for the classifiers tree view is implemented"
        )

    scicrunch = SciCrunch.get_instance(app)
    repo = ResearchResourceRepository(app)

    flat_tree_view = {}
    for resource in await repo.list_resources():
        try:
            validated_item = ClassifierItem(
                classifier=resource.rrid,
                display_name=resource.name.title(),
                short_description=resource.description,
                url=scicrunch.get_resolver_web_url(resource.rrid),
            )

            node = validated_item.display_name.replace(":", " ")
            flat_tree_view[node] = validated_item

        except ValidationError as err:
            logger.warning(
                "Cannot convert RRID into a classifier item. Skipping. Details: %s", err
            )

    return Classifiers.construct(classifiers=flat_tree_view).dict(exclude_unset=True)
