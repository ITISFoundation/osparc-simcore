from dataclasses import dataclass

from models_library.products import ProductName

#
# *Data are models used for rendering
#


@dataclass(frozen=True)
class JinjaTemplateDbGet:
    product_name: ProductName
    name: str
    content: str


@dataclass(frozen=True)
class UserData:
    first_name: str
    last_name: str
    email: str


@dataclass(frozen=True)
class ProductUIData:
    logo_url: str
    strong_color: str


@dataclass(frozen=True)
class ProductData:
    product_name: ProductName
    display_name: str
    vendor_display_inline: str
    support_email: str
    homepage_url: str
    ui: ProductUIData
