import logging

#
#
# FIXME: Temporary this is used as "sub-handlers" of start_pipeline handler
#   services/web/server/src/simcore_service_webserver/director_v2_handlers.py
#
#
from typing import List
from uuid import UUID

log = logging.getLogger(__file__)


async def get_meta_project_iterations(user_id: int, project_uuid: UUID) -> List[UUID]:
    """
    Returns a list of uuids of the iteration projects to run for a meta-project,
    otherwise it returns the project

    Creates separate snapshots of every iteration if not in place
    """
    return [
        project_uuid,
    ]
