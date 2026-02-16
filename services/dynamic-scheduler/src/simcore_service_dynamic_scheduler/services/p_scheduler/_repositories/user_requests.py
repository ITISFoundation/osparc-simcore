import sqlalchemy as sa
from models_library.api_schemas_dynamic_scheduler.dynamic_services import DynamicServiceStart, DynamicServiceStop
from models_library.projects_nodes_io import NodeID
from simcore_postgres_database.models.p_scheduler import ps_user_requests
from simcore_postgres_database.utils_repos import pass_or_acquire_connection, transaction_context
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ...base_repository import BaseRepository
from .._models import UserDesiredState, UserRequest


class UserRequestsRepository(BaseRepository):
    async def request_service_present(self, dynamic_service_start: DynamicServiceStart) -> None:
        # regardless of existence makes sure this entry exists

        insert_stmt = pg_insert(ps_user_requests).values(
            product_name=dynamic_service_start.product_name,
            user_id=dynamic_service_start.user_id,
            project_id=f"{dynamic_service_start.project_id}",
            node_id=dynamic_service_start.node_uuid,
            user_desired_state=UserDesiredState.PRESENT,
            payload=dynamic_service_start.model_dump(mode="json"),
        )
        upsert_stmt = insert_stmt.on_conflict_do_update(
            index_elements=[ps_user_requests.c.node_id],
            set_={
                "product_name": insert_stmt.excluded.product_name,
                "user_id": insert_stmt.excluded.user_id,
                "project_id": insert_stmt.excluded.project_id,
                "requested_at": sa.func.now(),
                "user_desired_state": insert_stmt.excluded.user_desired_state,
                "payload": insert_stmt.excluded.payload,
            },
        )
        async with transaction_context(self.engine) as conn:
            await conn.execute(upsert_stmt)

    async def request_service_absent(self, dynamic_service_stop: DynamicServiceStop) -> None:
        # regardless of existence makes sure this entry exists

        insert_stmt = pg_insert(ps_user_requests).values(
            product_name=dynamic_service_stop.product_name,
            user_id=dynamic_service_stop.user_id,
            project_id=f"{dynamic_service_stop.project_id}",
            node_id=dynamic_service_stop.node_id,
            user_desired_state=UserDesiredState.ABSENT,
            payload=dynamic_service_stop.model_dump(mode="json"),
        )
        upsert_stmt = insert_stmt.on_conflict_do_update(
            index_elements=[ps_user_requests.c.node_id],
            set_={
                "product_name": insert_stmt.excluded.product_name,
                "user_id": insert_stmt.excluded.user_id,
                "project_id": insert_stmt.excluded.project_id,
                "requested_at": sa.func.now(),
                "user_desired_state": insert_stmt.excluded.user_desired_state,
                "payload": insert_stmt.excluded.payload,
            },
        )
        async with transaction_context(self.engine) as conn:
            await conn.execute(upsert_stmt)

    async def get_user_request(self, node_id: NodeID) -> UserRequest | None:
        async with pass_or_acquire_connection(self.engine) as conn:
            result = await conn.execute(sa.select(ps_user_requests).where(ps_user_requests.c.node_id == node_id))
            row = result.first()
        if row is None:
            return None

        return UserRequest(
            product_name=row.product_name,
            user_id=row.user_id,
            project_id=row.project_id,
            node_id=row.node_id,
            requested_at=row.requested_at,
            user_desired_state=UserDesiredState(row.user_desired_state.value),
            payload=row.payload,
        )
