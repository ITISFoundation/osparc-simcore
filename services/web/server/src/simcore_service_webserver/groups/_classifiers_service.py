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

from aiohttp import web
from common_library.logging.logging_errors import create_troubleshooting_log_kwargs
from pydantic import (
    BaseModel,
    Field,
    HttpUrl,
    StringConstraints,
    TypeAdapter,
    ValidationError,
    field_validator,
)

from ..scicrunch.errors import ScicrunchError
from ..scicrunch.scicrunch_service import SCICRUNCH_SERVICE_APPKEY
from ._classifiers_repository import GroupClassifierRepository

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
    url: Annotated[
        HttpUrl | None,
        Field(
            description="Link to more information",
            examples=["https://scicrunch.org/resources/Any/search?q=osparc&l=osparc"],
        ),
    ] = None

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


# SERVICE LAYER --------


class GroupClassifiersService:
    def __init__(self, app: web.Application):
        self.app = app
        self._repo = GroupClassifierRepository.create_from_app(app)

    async def get_group_classifiers(
        self, gid: int, tree_view_mode: Literal["std"] = "std"
    ) -> dict[str, Any]:
        """Get classifiers for a group, either from bundle or dynamic tree view."""
        if not await self._repo.group_uses_scicrunch(gid):
            bundle = await self._repo.get_classifiers_from_bundle(gid)
            if bundle:
                try:
                    # truncate bundle to what is needed and drop the rest
                    return Classifiers(**bundle).model_dump(
                        exclude_unset=True, exclude_none=True
                    )
                except ValidationError as err:
                    _logger.exception(
                        **create_troubleshooting_log_kwargs(
                            f"DB corrupt data in 'groups_classifiers' table. Invalid classifier for gid={gid}. Returning empty bundle.",
                            error=err,
                            error_context={
                                "gid": gid,
                                "bundle": bundle,
                            },
                        )
                    )
            return {}

        # otherwise, build dynamic tree with RRIDs
        try:
            return await self._build_rrids_tree_view(tree_view_mode=tree_view_mode)
        except ScicrunchError:
            # Return empty view on any error (including ScicrunchError)
            return {}

    async def _build_rrids_tree_view(
        self, tree_view_mode: Literal["std"] = "std"
    ) -> dict[str, Any]:
        if tree_view_mode != "std":
            msg = "Currently only 'std' option for the classifiers tree view is implemented"
            raise NotImplementedError(msg)

        service = self.app[SCICRUNCH_SERVICE_APPKEY]

        flat_tree_view: dict[TreePath, ClassifierItem] = {}
        for resource in await service.list_research_resources():
            try:
                validated_item = ClassifierItem(
                    classifier=resource.rrid,
                    display_name=resource.name.title(),
                    short_description=resource.description,
                    url=service.get_resolver_web_url(resource.rrid),
                )

                node = TypeAdapter(TreePath).validate_python(
                    validated_item.display_name.replace(":", " ")
                )
                flat_tree_view[node] = validated_item

            except ValidationError as err:
                _logger.warning(
                    "Cannot convert RRID into a classifier item. Skipping. Details: %s",
                    err,
                )

        return Classifiers.model_construct(classifiers=flat_tree_view).model_dump(
            exclude_unset=True
        )
