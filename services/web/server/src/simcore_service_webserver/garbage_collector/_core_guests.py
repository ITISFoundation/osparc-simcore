import asyncio
import itertools
import logging

import asyncpg.exceptions
from aiohttp import web
from models_library.projects import ProjectID
from models_library.users import UserID, UserNameID
from redis.asyncio import Redis
from servicelib.common_headers import UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
from simcore_postgres_database.aiopg_errors import DatabaseError
from simcore_postgres_database.models.users import UserRole

from ..projects._projects_repository_legacy import ProjectDBAPI
from ..projects._projects_service import (
    get_project_for_user,
    submit_delete_project_task,
)
from ..projects.exceptions import ProjectDeleteError, ProjectNotFoundError
from ..redis import get_redis_lock_manager_client
from ..resource_manager.registry import RedisResourceRegistry
from ..users import exceptions, users_service
from ..users.exceptions import UserNotFoundError
from ._core_utils import get_new_project_owner_gid, replace_current_owner
from .settings import GUEST_USER_RC_LOCK_FORMAT

_logger = logging.getLogger(__name__)


async def _delete_all_projects_for_user(app: web.Application, user_id: int) -> None:
    """
    Goes through all the projects and will try to remove them but first it will check if
    the project is shared with others.
    Based on the given access rights it will determine the action to take:
    - if other users have read access & execute access it will get deleted
    - if other users have write access the project's owner will be changed to a new owner:
        - if the project is directly shared with  one or more users, one of these
            will be picked as the new owner
        - if the project is not shared with any user but with groups of users, one
            of the users inside the group (which currently exists) will be picked as
            the new owner
    """
    # recover user's primary_gid
    try:
        project_owner_primary_gid = await users_service.get_user_primary_group_id(
            app=app, user_id=user_id
        )
    except exceptions.UserNotFoundError:
        _logger.warning(
            "Could not recover user data for user '%s', stopping removal of projects!",
            f"{user_id=}",
        )
        return

    # fetch all projects for the user
    user_project_uuids = await ProjectDBAPI.get_from_app_context(
        app
    ).list_projects_uuids(user_id=user_id)

    _logger.info(
        "Removing or transfering projects of user with %s, %s: %s",
        f"{user_id=}",
        f"{project_owner_primary_gid=}",
        f"{user_project_uuids=}",
    )

    delete_tasks: list[asyncio.Task] = []

    for project_uuid in user_project_uuids:
        try:
            project: dict = await get_project_for_user(
                app=app,
                project_uuid=project_uuid,
                user_id=user_id,
            )
        except (web.HTTPNotFound, ProjectNotFoundError) as err:
            _logger.warning(
                "Could not find project %s for user with %s to be removed: %s. Skipping.",
                f"{project_uuid=}",
                f"{user_id=}",
                f"{err}",
            )
            continue

        assert project  # nosec

        new_project_owner_gid = await get_new_project_owner_gid(
            app=app,
            project_uuid=project_uuid,
            user_id=user_id,
            user_primary_gid=project_owner_primary_gid,
            project=project,
        )

        if new_project_owner_gid is None:
            # when no new owner is found just remove the project
            try:
                _logger.debug(
                    "Removing project %s from user with %s",
                    f"{project_uuid=}",
                    f"{user_id=}",
                )
                task = await submit_delete_project_task(
                    app,
                    ProjectID(project_uuid),
                    user_id,
                    UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
                )
                assert task  # nosec
                delete_tasks.append(task)

            except ProjectNotFoundError:
                logging.warning(
                    "Project with %s was not found, skipping removal",
                    f"{project_uuid=}",
                )

        else:
            # Try to change the project owner and remove access rights from the current owner
            _logger.debug(
                "Transferring ownership of project %s from user %s to %s.",
                "This project cannot be removed since it is shared with other users"
                f"{project_uuid=}",
                f"{user_id}",
                f"{new_project_owner_gid}",
            )
            await replace_current_owner(
                app=app,
                project_uuid=project_uuid,
                user_primary_gid=project_owner_primary_gid,
                new_project_owner_gid=new_project_owner_gid,
                project=project,
            )

    # NOTE: ensures all delete_task tasks complete or fails fast
    # can raise ProjectDeleteError, CancellationError
    await asyncio.gather(*delete_tasks)


async def remove_guest_user_with_all_its_resources(
    app: web.Application, user_id: int
) -> None:
    """Removes a GUEST user with all its associated projects and S3/MinIO files"""

    try:
        user_role: UserRole = await users_service.get_user_role(app, user_id=user_id)
        if user_role > UserRole.GUEST:
            # NOTE: This acts as a protection barrier to avoid removing resources to more
            # priviledge users
            return

        _logger.debug(
            "Deleting all projects of user with %s because it is a GUEST",
            f"{user_id=}",
        )
        await _delete_all_projects_for_user(app=app, user_id=user_id)

        _logger.debug(
            "Deleting user %s because it is a GUEST",
            f"{user_id=}",
        )
        await users_service.delete_user_without_projects(app, user_id)

    except (
        DatabaseError,
        asyncpg.exceptions.PostgresError,
        ProjectNotFoundError,
        UserNotFoundError,
        ProjectDeleteError,
    ) as error:
        _logger.warning(
            "Failed to delete guest user %s and its resources: %s",
            f"{user_id=}",
            f"{error}",
        )


async def remove_users_manually_marked_as_guests(
    registry: RedisResourceRegistry, app: web.Application
) -> None:
    """
    Removes all the projects MANUALLY marked as GUEST users in the system (i.e. does not include
    those accessing via the front-end).
    If the user defined a TEMPLATE, this one also gets removed.
    """
    redis_locks_client: Redis = get_redis_lock_manager_client(app)

    # collects all users with registed sessions
    (
        all_user_session_alive,
        all_user_sessions_dead,
    ) = await registry.get_all_resource_keys()

    skip_users = {
        int(user_session["user_id"])
        for user_session in itertools.chain(
            all_user_session_alive, all_user_sessions_dead
        )
    }

    # Prevent creating this list if a guest user
    guest_users: list[tuple[UserID, UserNameID]] = (
        await users_service.get_guest_user_ids_and_names(app)
    )

    for guest_user_id, guest_user_name in guest_users:
        # Prevents removing GUEST users that were automatically (NOT manually) created
        # from the front-end
        if guest_user_id in skip_users:
            _logger.debug(
                "Skipping garbage-collecting GUEST user with %s since it still has resources in use",
                f"{guest_user_id=}",
            )
            continue

        # Prevents removing GUEST users that are initializating
        lock_during_construction: bool = await redis_locks_client.lock(
            GUEST_USER_RC_LOCK_FORMAT.format(user_id=guest_user_name)
        ).locked()

        lock_during_initialization: bool = await redis_locks_client.lock(
            GUEST_USER_RC_LOCK_FORMAT.format(user_id=guest_user_id)
        ).locked()

        if lock_during_construction or lock_during_initialization:
            _logger.debug(
                "Skipping garbage-collecting GUEST user with %s and %s since it is still locked",
                f"{guest_user_id=}",
                f"{guest_user_name=}",
            )
            continue

        # Removing
        _logger.info(
            "Removing user %s and %s with all its resources because it was MARKED as GUEST",
            f"{guest_user_id=}",
            f"{guest_user_name=}",
        )
        await remove_guest_user_with_all_its_resources(
            app=app,
            user_id=guest_user_id,
        )

        await remove_guest_user_with_all_its_resources(
            app=app,
            user_id=guest_user_id,
        )
