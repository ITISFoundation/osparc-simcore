"""Applies a user's accessible default tags to newly created studies."""

from aiohttp import web
from models_library.products import ProductName
from models_library.shared_user_preferences import DefaultStudyTagIdsFrontendUserPreference
from models_library.users import UserID

from ..tags import tags_service
from ..user_preferences import user_preferences_service
from .models import ProjectDict


async def apply_user_default_tags(
    app: web.Application,
    *,
    project: ProjectDict,
    user_id: UserID,
    product_name: ProductName,
) -> ProjectDict:
    """Merge accessible user defaults into project tags and discard stale defaults."""
    preference = await user_preferences_service.get_frontend_user_preference(
        app,
        user_id,
        product_name,
        DefaultStudyTagIdsFrontendUserPreference,
    )
    if not isinstance(preference, DefaultStudyTagIdsFrontendUserPreference):
        return project

    accessible_tag_ids = {tag.id for tag in await tags_service.list_tags(app, user_id)}
    valid_default_tag_ids = list(dict.fromkeys(tag_id for tag_id in preference.value if tag_id in accessible_tag_ids))

    if valid_default_tag_ids != preference.value:
        await user_preferences_service.set_frontend_user_preference(
            app,
            user_id=user_id,
            product_name=product_name,
            frontend_preference_identifier=preference.preference_identifier,
            value=valid_default_tag_ids,
            expected_preference=preference,
        )

    project["tags"] = list(dict.fromkeys([*project.get("tags", []), *valid_default_tag_ids]))
    return project
