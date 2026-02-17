"""Helper functions for creating notification data models."""

from aiohttp import web
from models_library.emails import LowerCaseEmailStr
from models_library.products import ProductName
from notifications_library._models import (
    ProductData,
    ProductFooterData,
    ProductUIData,
    UserData,
)

from ..products.products_service import get_product


def get_product_data(
    app: web.Application,
    *,
    product_name: ProductName,
) -> ProductData:
    product = get_product(app, product_name=product_name)

    # Extract vendor information
    vendor_display_inline = (
        str(product.vendor.get("name"))
        if product.vendor and product.vendor.get("name") is not None
        else "IT'IS Foundation"
    )

    # Extract UI information from product.vendor.ui (optional)
    ui_data = ProductUIData(
        logo_url=(product.vendor.get("ui", {}).get("logo_url") if product.vendor else None),
        strong_color=(product.vendor.get("ui", {}).get("strong_color") if product.vendor else None),
    )

    homepage_url = product.vendor.get("url") if product.vendor else None

    footer_data = ProductFooterData(
        social_links=product.vendor.get("footer_social_links", []) if product.vendor else [],
        share_links=product.vendor.get("footer_share_links", []) if product.vendor else [],
        company_name=product.vendor.get("company_name", "") if product.vendor else "",
        company_address=product.vendor.get("company_address", "") if product.vendor else "",
        company_links=product.vendor.get("company_links", []) if product.vendor else [],
    )

    return ProductData(
        product_name=product_name,
        display_name=product.display_name,
        vendor_display_inline=vendor_display_inline,
        support_email=product.support_email,
        homepage_url=homepage_url,
        ui=ui_data,
        footer=footer_data,
    )


def create_user_data(
    *,
    user_email: LowerCaseEmailStr,
    first_name: str,
    last_name: str,
) -> UserData:
    return UserData(
        user_name=f"{first_name} {last_name}".strip(),
        email=user_email,
        first_name=first_name,
        last_name=last_name,
    )
