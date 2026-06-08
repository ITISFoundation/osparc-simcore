import sqlalchemy as sa
from models_library.products import ProductName
from simcore_postgres_database.models.products import products

from ...models.product import (
    CompanyLink,
    ProductData,
    ProductFooterData,
    ProductUIData,
    SocialLink,
)
from .._db_base import BaseRepository

_PRODUCT_COLUMNS = (
    products.c.name,
    products.c.display_name,
    products.c.support_email,
    products.c.vendor,
)


class ProductRepository(BaseRepository):
    async def get_product_data(self, product_name: ProductName) -> ProductData:
        async with self.engine.connect() as conn:
            row = (await conn.execute(sa.select(*_PRODUCT_COLUMNS).where(products.c.name == product_name))).one()

        vendor: dict = row.vendor or {}

        return ProductData(
            product_name=row.name,
            display_name=row.display_name,
            vendor_display_inline=vendor.get("name", "IT'IS Foundation"),
            support_email=row.support_email,
            homepage_url=vendor.get("url"),
            ui=ProductUIData(
                logo_url=vendor.get("ui", {}).get("logo_url"),
                strong_color=vendor.get("ui", {}).get("strong_color"),
            ),
            footer=ProductFooterData(
                social_links=[SocialLink(name=name, url=url) for name, url in vendor.get("footer_social_links", [])],
                company_name=vendor.get("company_name", ""),
                company_address=vendor.get("company_address", ""),
                company_links=[CompanyLink(name=name, url=url) for name, url in vendor.get("company_links", [])],
            ),
        )
