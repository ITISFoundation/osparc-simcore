# import logging

# import sqlalchemy as sa
# from models_library.api_schemas_catalog import UserInaccessibleService
# from models_library.services import ServiceKeyVersion
# from models_library.users import GroupID
# from simcore_postgres_database.models.groups import user_to_groups
# from sqlalchemy.sql import and_, or_

# from ..tables import services_access_rights
# from ._base import BaseRepository

# logger = logging.getLogger(__name__)


# class ShareableServicesRepository(BaseRepository):
#     """
#     API that operates on services_access_rights and user_to_groups tables
#     """

#     async def list_group_users_inaccesible_services(
#         self,
#         gid: GroupID,
#         product_name: str,
#         services_to_check: list[ServiceKeyVersion],
#     ) -> list[UserInaccessibleService]:
#         async with self.db_engine.begin() as conn:
#             stmts = [
#                 sa.select(
#                     sa.literal(service.key).label("service_key"),
#                     sa.literal(service.version).label("service_version"),
#                 )
#                 for service in services_to_check
#             ]
#             services_to_check_table = sa.union_all(*stmts).cte(
#                 name="services_to_check_table"
#             )

#             users_ids = (
#                 sa.select(user_to_groups.c.uid)
#                 .where(user_to_groups.c.gid == gid)
#                 .cte("users_ids")
#             )

#             users_gids = (
#                 sa.select(user_to_groups.c.uid, user_to_groups.c.gid)
#                 .where(user_to_groups.c.uid.in_(users_ids))
#                 .cte("users_gids")
#             )

#             users_services = (
#                 sa.select(
#                     users_gids.c.uid,
#                     services_access_rights.c.key,
#                     services_access_rights.c.version,
#                 )
#                 .join(
#                     users_gids,
#                     and_(
#                         services_access_rights.c.gid == users_gids.c.gid,
#                         services_access_rights.c.product_name == product_name,
#                     ),
#                 )
#                 .distinct()
#                 .cte("users_services")
#             )

#             # Cross join (cartesian product) between services_to_check_table and users_services
#             services_to_check_table_modified = sa.select(
#                 users_ids.c.uid,
#                 services_to_check_table.c.service_key,
#                 services_to_check_table.c.service_version,
#             ).cte("services_to_check_table_modified")

#             final_statement = (
#                 sa.select(
#                     services_to_check_table_modified.c.uid,
#                     services_to_check_table_modified.c.service_key,
#                     services_to_check_table_modified.c.service_version,
#                 )
#                 .join(
#                     users_services,
#                     and_(
#                         services_to_check_table_modified.c.service_key
#                         == users_services.c.key,
#                         services_to_check_table_modified.c.service_version
#                         == users_services.c.version,
#                         services_to_check_table_modified.c.uid == users_services.c.uid,
#                     ),
#                     isouter=True,
#                 )
#                 .where(
#                     or_(users_services.c.key == None, users_services.c.version == None)
#                 )
#             )

#             result = await conn.execute(final_statement)
#             users_without_service_access: list[UserInaccessibleService] = [
#                 UserInaccessibleService(
#                     user_primary_group=row[0],
#                     service_key=row[1],
#                     service_version=row[2],
#                 )
#                 for row in result.fetchall()
#             ]
#             return users_without_service_access
