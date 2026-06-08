from dataclasses import dataclass
from typing import NamedTuple

from models_library.products import ProductName


@dataclass(frozen=True)
class ProductUIData:
    logo_url: str | None = None
    strong_color: str | None = None


class SocialLink(NamedTuple):
    name: str
    url: str


class CompanyLink(NamedTuple):
    name: str
    url: str


type FooterSocialLinks = list[SocialLink]
type CompanyLinks = list[CompanyLink]


@dataclass(frozen=True)
class ProductFooterData:
    social_links: FooterSocialLinks
    company_name: str
    company_address: str
    company_links: CompanyLinks


@dataclass(frozen=True)
class ProductData:
    product_name: ProductName
    display_name: str
    vendor_display_inline: str
    support_email: str
    homepage_url: str | None
    ui: ProductUIData
    footer: ProductFooterData

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
