"""
    Every group can define classifiers by storing a bundle in the group_classifiers table.
        - This bundle is a static tree resulting from curation process that is outsourced (e.g. to a github/lab repository)

"""

import logging
from typing import Any, Dict, Optional

import sqlalchemy as sa
from aiohttp import web

# DATABASE --------
from pydantic import BaseModel, Field, HttpUrl, ValidationError, constr

from .constants import APP_DB_ENGINE_KEY
from .db_models import group_classifiers
from .scicrunch_api import SciCrunchAPI

# HELPERS FOR API --------------
from .scicrunch_db import ResearchResourceRepository

logger = logging.getLogger(__name__)

# API SCHEMAS ---

TreePath = constr(regex=r"[\w:]+")  # Examples 'a::b::c


class ClassifierItem(BaseModel):
    classifier: str = Field(
        ..., description="Unique identifier used to tag studies or services", example=""
    )
    display_name: str
    short_description: Optional[str]  # TODO: truncate
    url: Optional[HttpUrl] = Field(
        None,
        description="Link to more information",
        example="https://scicrunch.org/resources/Any/search?q=osparc&l=osparc",
    )


class Classifiers(BaseModel):
    # meta
    vcs_url: Optional[str]
    vcs_ref: Optional[str]

    # data
    classifiers: Dict[TreePath, ClassifierItem]


class GroupClassifierRepository:
    def __init__(self, app: web.Application):
        self.engine = app[APP_DB_ENGINE_KEY]

    async def get_bundle(self, gid: int) -> Dict[str, Any]:
        async with self.engine.acquire() as conn:
            bundle = await conn.scalar(
                sa.select([group_classifiers.c.bundle]).where(
                    group_classifiers.c.gid == gid
                )
            )
            return bundle or {}

    async def get_validated_bundle(self, gid: int) -> Dict[str, Any]:
        bundle = await self.get_bundle(gid)
        if bundle:
            try:
                # truncate bundle to what is needed and drop the rest
                bundle = Classifiers(**bundle).dict(exclude_unset=True)
            except ValidationError as err:
                logger.error(
                    "Fix invalid entry in group_classifiers table for gid=%d: %s. Returning empty bundle.",
                    gid,
                    err,
                )
                bundle = {}
        return bundle

    async def uses_rrids(self, gid: int) -> bool:
        async with self.engine.acquire() as conn:
            return await conn.scalar(
                sa.select([group_classifiers.c.uses_scicrunch_rrids]).where(
                    group_classifiers.c.gid == gid
                )
            )


async def build_rrids_tree_view(app, tree_view_mode="std"):
    if tree_view_mode != "std":
        raise web.HTTPNotImplemented(
            reason="Currently only 'std' option for the classifiers tree view is implemented"
        )

    scicrunch = SciCrunchAPI.get_instance(app)
    repo = ResearchResourceRepository(app)

    flat_tree_view = {}
    for resource in await repo.list_all():
        try:
            validated_item = ClassifierItem(
                classifier=resource.rrid,
                display_name=resource.name.title().strip(),
                short_description=resource.description,
                url=scicrunch.get_rrid_link(resource.rrid),
            )

            node = validated_item.display_name.replace(":", " ")
            flat_tree_view[node] = validated_item

        except ValidationError as err:
            logger.warning(
                "Cannot convert RRID into a classifier item. Skipping. Details: %s", err
            )

    return Classifiers.construct(classifiers=flat_tree_view)
