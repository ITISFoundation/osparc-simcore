import logging

from aiohttp import web
from models_library.computations import CollectionRunID

from ..db.plugin import get_database_engine
from . import _comp_run_collections_repository
from ._comp_run_collections_models import CompRunCollectionDBGet

_logger = logging.getLogger(__name__)


async def create_comp_run_collection(
    app: web.Application,
    client_or_system_generated_id: str,
    client_or_system_generated_display_name: str,
    generated_by_system: bool,
) -> CollectionRunID:
    """raises: ProjectNotFoundError"""
    async with get_database_engine(app).acquire() as conn:
        return await _comp_run_collections_repository.create_comp_run_collection(
            conn=conn,
            client_or_system_generated_id=client_or_system_generated_id,
            client_or_system_generated_display_name=client_or_system_generated_display_name,
            generated_by_system=generated_by_system,
        )


async def get_comp_run_collection_or_none_by_id(
    app: web.Application, collection_run_id: CollectionRunID
) -> CompRunCollectionDBGet | None:
    async with get_database_engine(app).acquire() as conn:
        return await _comp_run_collections_repository.get_comp_run_collection_or_none_by_id(
            conn=conn, collection_run_id=collection_run_id
        )


async def get_comp_run_collection_or_none_by_client_generated_id(
    app: web.Application,
    client_or_system_generated_id: str,
) -> CompRunCollectionDBGet | None:
    async with get_database_engine(app).acquire() as conn:
        return await _comp_run_collections_repository.get_comp_run_collection_or_none_by_client_generated_id(
            conn=conn, client_or_system_generated_id=client_or_system_generated_id
        )
