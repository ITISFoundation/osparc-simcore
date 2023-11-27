import sqlalchemy as sa
from aiopg.sa.result import RowProxy
from models_library.resource_tracker import HardwareInfo, PricingUnitId

from ....core.errors import ResourceTrackerPricingUnitsError
from ..tables import resource_tracker_pricing_units
from ._base import BaseRepository


class ResourceTrackerPricingUnitsRepository(BaseRepository):
    async def get_hardware_info(self, pricing_unit_id: PricingUnitId) -> HardwareInfo:
        """
        Raises:
            ResourceTrackerPricingUnitsError
        """
        async with self.db_engine.acquire() as conn:
            row: RowProxy | None = await (
                await conn.execute(
                    sa.select(resource_tracker_pricing_units.c.specific_info).where(
                        resource_tracker_pricing_units.c.pricing_unit_id
                        == pricing_unit_id
                    )
                )
            ).first()
        if not row:
            raise ResourceTrackerPricingUnitsError(pricing_unit_id=pricing_unit_id)
        return HardwareInfo.from_orm(row)
