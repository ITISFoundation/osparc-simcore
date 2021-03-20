"""

Draft Rationale:

    osparc-simcore defines TWO authorization methods: i.e. a set of rules on what,
    how and when any resource can be accessed or operated by a user

    ROLE-BASED METHOD:
    In this method, a user is assigned a role (user/tester/admin) upon registration. Each role is
    system-wide and defines a set of operations that the user *can* perform
        - Every operation is named as a resource and an action (e.g. )
        - Resource is named hierarchically
        - Roles can inherit permitted operations from other role
    This method is static because is system-wide and it is defined directly in the
    code at services/web/server/src/simcore_service_webserver/security_roles.py
    It is defined on top of every API entrypoint and applied just after authentication of the user.

    GROUP-BASED METHOD:
    The second method is designed to share a resource among groups of users dynamically. A group
    defines a set of rules that apply to a resource and users can be added to the group dynamically.
    So far, there are two resources that define access rights (AR):
        - one applies to projects (read/write/delete) and
        - the other to services (execute/write)
    The project access rights are set in the column "access_rights" of the "projects" table .
    The service access rights has its own table: service_access_rights

    Access rights apply hierarchically, meaning that the access granted to a project applies
    to all nodes inside and stored data in nodes.

    How do these two AR coexist?: Access to read, write or delete a project are defined in the project AR but execution
    will depend on the service AR attached to nodes inside.


    What about stored data?
    - nodes data are stored in s3 hierarchically and inherits the AR from the associated project
    -
    - Some s3 data objects are associated with nodes in a project
    - Access to a project is also regulated via access rights and it is also
    the case for all data objects under this project
"""


from dataclasses import dataclass
from typing import Dict, List

from aiopg.sa.connection import SAConnection
from sqlalchemy.sql import text

# import sqlalchemy as sa
# from aiopg.sa.result import ResultProxy, RowProxy
# from simcore_postgres_database.storage_models import (
#    file_meta_data,
#    projects,
#    user_to_groups,
# )


ProjectID = str


@dataclass
class AccessRights:
    read: bool = False
    write: bool = False
    delete: bool = False


async def get_projects_access_rights(
    conn: SAConnection, user_id: int
) -> Dict[ProjectID, AccessRights]:
    """ Returns projects included in any user's group and its access rights """

    smt = text(
        f"""\
    SELECT uuid, access_rights
    FROM projects
    WHERE (
        prj_owner = {user_id}
        OR jsonb_exists_any( access_rights, (
               SELECT ARRAY( SELECT gid::TEXT FROM user_to_groups WHERE uid = {user_id} )
            )
        )
    )
    """
    )

    projects_access_rights = {}

    async for row in conn.execute(smt):
        prj_access = {"read": False, "write": False, "delete": False}
        for grp_access in row.access_rights.values():
            for key in grp_access:
                prj_access[key] |= grp_access[key]

        assert isinstance(row.uuid, ProjectID)
        projects_access_rights[row.uuid] = AccessRights(**prj_access)
    return projects_access_rights


async def get_readable_project_ids(conn: SAConnection, user_id: int) -> List[ProjectID]:
    projects_access_rights = await get_projects_access_rights(conn, int(user_id))
    return [pid for pid, access in projects_access_rights.items() if access.read]
