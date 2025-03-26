from dataclasses import dataclass
from pydantic import HttpUrl

from models_library.products import ProductName


#
# *Data are models used for rendering
#
@dataclass(frozen=True)
class UserData:
    first_name: str
    last_name: str
    email: str


@dataclass(frozen=True)
class ProductData:
    product_name: ProductName
    display_name: str
    vendor_display_inline: str
    support_email: str
    product_logo: HttpUrl = "https://raw.githubusercontent.com/ITISFoundation/osparc-simcore/refs/heads/master/services/static-webserver/client/source/resource/osparc/osparc-black.svg"
    product_homepage: HttpUrl = "https://osparc.io/"
