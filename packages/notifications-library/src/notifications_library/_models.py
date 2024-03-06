from dataclasses import dataclass

from models_library.products import ProductName


@dataclass
class UserData:
    first_name: str
    last_name: str
    email: str


@dataclass
class ProductData:
    product_name: ProductName
    display_name: str
    vendor_display_inline: str
    support_email: str
