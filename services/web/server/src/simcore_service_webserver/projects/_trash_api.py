import arrow
from aiohttp import web
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.users import UserID

from . import projects_api
from .models import ProjectPatchExtended


async def empty_trash(app: web.Application, product_name: ProductName, user_id: UserID):
    # filter trashed=True and set them to False
    raise NotImplementedError


async def update_project(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    project_id: ProjectID,
    trashed: bool,
):
    # FIXME: can you trash something that is running?

    await projects_api.patch_project(
        app,
        user_id=user_id,
        product_name=product_name,
        project_uuid=project_id,
        project_patch=ProjectPatchExtended(
            trashed_at=arrow.utcnow().datetime if trashed else None
        ),
    )
