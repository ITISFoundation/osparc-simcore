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
class ProductFooterData:
    social_links: list[tuple[str, str]]  # list of (social_media_name, social_media_url)
    share_links: list[tuple[str, str, str]]  # list of (share_name, share_label, share_url)
    company_name: str
    company_address: str
    company_links: list[tuple[str, str]]  # list of (link_name, link_url)


@dataclass(frozen=True)
class ProductData:
    product_name: ProductName
    display_name: str
    vendor_display_inline: str
    support_email: str
    homepage_url: str | None  # default_homepage = "https://osparc.io/" in base.html
    ui: ProductUIData
    footer: ProductFooterData

    @property
    def footer_social_links(self) -> list[tuple[str, str]]:
        return self.footer.social_links

    @property
    def footer_share_links(self) -> list[tuple[str, str, str]]:
        return self.footer.share_links

    @property
    def company_name(self) -> str:
        return self.footer.company_name

    @property
    def company_address(self) -> str:
        return self.footer.company_address

    @property
    def company_links(self) -> list[tuple[str, str]]:
        return self.footer.company_links
