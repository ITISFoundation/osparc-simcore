from dataclasses import dataclass
from typing import NamedTuple

from models_library.products import ProductName


@dataclass(frozen=True)
class UserData:
    user_name: str
    first_name: str
    last_name: str
    email: str


@dataclass(frozen=True)
class Sharer:
    user_name: str
    message: str


@dataclass(frozen=True)
class ProductUI:
    logo_url: str | None = (
        None  # default_logo = "https://raw.githubusercontent.com/ITISFoundation/osparc-simcore/refs/heads/master/services/static-webserver/client/source/resource/osparc/osparc-white.svg" in base.html  # noqa: E501
    )
    strong_color: str | None = None  # default_strong_color = "rgb(131, 0, 191)" in base.html


class SocialLink(NamedTuple):
    name: str  # e.g. "youtube", "linkedin", "github"
    url: str  # e.g. "https://youtube.com/@company", "https://www.linkedin.com/@company", "https://github.com/ITISFoundation/osparc-simcore"


class CompanyLink(NamedTuple):
    name: str  # e.g. "osparc.io", "sim4life"
    url: str  # e.g. "https://osparc.io/about/", "https://sim4life.swiss/"


# --- type aliases (PEP 695) ---
type FooterSocialLinks = list[SocialLink]
type CompanyLinks = list[CompanyLink]


@dataclass(frozen=True)
class ProductFooter:
    social_links: FooterSocialLinks
    company_name: str
    company_address: str
    company_links: CompanyLinks


@dataclass(frozen=True)
class Product:
    name: ProductName
    display_name: str
    vendor_display_inline: str
    support_email: str
    homepage_url: str | None  # default_homepage = "https://osparc.io/" in base.html
    ui: ProductUI
    footer: ProductFooter

    @property
    def footer_social_links(self) -> FooterSocialLinks:
        return self.footer.social_links

    @property
    def company_name(self) -> str:
        return self.footer.company_name

    @property
    def company_address(self) -> str:
        return self.footer.company_address

    @property
    def company_links(self) -> CompanyLinks:
        return self.footer.company_links
