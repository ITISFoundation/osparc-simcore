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
    user_name: str
    first_name: str
    last_name: str
    email: str


@dataclass(frozen=True)
class SharerData:
    user_name: str
    message: str


@dataclass(frozen=True)
class ProductUIData:
    logo_url: str | None = (
        None  # default_logo = "https://raw.githubusercontent.com/ITISFoundation/osparc-simcore/refs/heads/master/services/static-webserver/client/source/resource/osparc/osparc-white.svg" in base.html  # noqa: E501
    )
    strong_color: str | None = None  # default_strong_color = "rgb(131, 0, 191)" in base.html


@dataclass(frozen=True)
class ProductData:
    product_name: ProductName
    display_name: str
    vendor_display_inline: str
    support_email: str
    homepage_url: str | None  # default_homepage = "https://osparc.io/" in base.html
    ui: ProductUIData
    footer_social_links: list[tuple[str, str]]  # list of (social_media_name (youtube, linkedin), social_media_url)
    footer_share_links: list[tuple[str, str, str]]  # list of (share_name, share_label, share_url)
    company_name: str
    company_address: str
    company_links: list[tuple[str, str]]  # list of (link_name, link_url)
