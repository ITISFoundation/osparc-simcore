from dataclasses import dataclass

from models_library.basic_types import VersionStr
from models_library.products import ProductName
from models_library.rest_pagination import (
    DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    PageLimitInt,
    PageMetaInfoLimitOffset,
    PageOffsetInt,
)
from models_library.users import UserID
from servicelib.fastapi.app_state import SingletonInAppStateMixin
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.catalog import services as catalog_rpc

from ..models.schemas.solvers import Solver, SolverKeyId, SolverPort

_FAKE: list[Solver] = [
    Solver.model_validate(Solver.model_json_schema()["example"]),
]
_FAKE2: list[SolverPort] = [
    SolverPort.model_validate(SolverPort.model_json_schema()["example"]),
]
# from models_library.api_schemas_catalog.services import (
#     LatestServiceGet,
#     MyServiceGet,
#     ServiceGetV2,
#     ServiceUpdateV2,
# )

assert catalog_rpc  # nosec


@dataclass
class CatalogService(SingletonInAppStateMixin):
    app_state_name = "CatalogService"
    _client: RabbitMQRPCClient

    async def list_latest_releases(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        offset: PageOffsetInt = 0,
        limit: PageLimitInt = DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    ) -> tuple[list[Solver], PageMetaInfoLimitOffset]:
        assert product_name  # nosec
        assert user_id  # nosec

        data = _FAKE[offset : offset + limit]
        meta = PageMetaInfoLimitOffset(
            limit=limit, offset=offset, total=len(_FAKE), count=len(data)
        )
        return data, meta

    async def list_solver_releases(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        solver_id: SolverKeyId,
        offset: PageOffsetInt = 0,
        limit: PageLimitInt = DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    ) -> tuple[list[Solver], PageMetaInfoLimitOffset]:
        assert product_name  # nosec
        assert user_id  # nosec

        data = [solver for solver in _FAKE if solver.id == solver_id][
            offset : offset + limit
        ]

        meta = PageMetaInfoLimitOffset(
            limit=limit, offset=offset, total=len(_FAKE), count=len(data)
        )
        return data, meta

    async def get_solver(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        solver_id: SolverKeyId,
        solver_version: VersionStr,
    ) -> Solver | None:
        assert product_name  # nosec
        assert user_id  # nosec

        # service: ServiceGetV2 = await catalog_rpc.get_service(
        #     get_rabbitmq_rpc_client(app),
        #     product_name=product_name,
        #     user_id=user_id,
        #     service_key=solver_id,
        #     service_version=solver_version,
        # )

        # solver = Solver(id=service.key, version=service.version, title=) ServiceGetV2)(service)

        return next(
            (
                solver
                for solver in _FAKE
                if solver.id == solver_id and solver.version == solver_version
            ),
            None,
        )

    async def get_solver_ports(
        self,
        *,
        product_name: ProductName,
        user_id: int,
        solver_id: SolverKeyId,
        solver_version: VersionStr,
    ) -> list[SolverPort]:

        if await self.get_solver(
            product_name=product_name,
            user_id=user_id,
            solver_id=solver_id,
            solver_version=solver_version,
        ):
            return _FAKE2
        return []
