from typing import Literal

from common_library.pydantic_basic_types import NotEmptyStr
from models_library.products import ProductName
from pydantic import BaseModel, EmailStr


class UserData(BaseModel):
    username: str
    first_name: str
    last_name: str
    email: EmailStr

    # TODO: add more fields as needed


class ProductUIData(BaseModel):
    project_alias: str
    logo_url: str | None = (
        None  # default_logo = "https://raw.githubusercontent.com/ITISFoundation/osparc-simcore/refs/heads/master/services/static-webserver/client/source/resource/osparc/osparc-white.svg" in base.html
    )
    strong_color: str | None = (
        None  # default_strong_color = "rgb(131, 0, 191)" in base.html
    )


class ProductData(BaseModel):
    product_name: ProductName
    display_name: str
    vendor_display_inline: str
    support_email: str
    homepage_url: str | None  # default_homepage = "https://osparc.io/" in base.html
    ui: ProductUIData


class AccountRequestedEvent(BaseModel):
    type: Literal["account_requested"] = "account_requested"

    user: UserData
    product: ProductData
    host: str


class AccountApprovedEvent(BaseModel):
    type: Literal["account_approved"] = "account_approved"


class AccountRejectedEvent(BaseModel):
    type: Literal["account_rejected"] = "account_rejected"

    reason: NotEmptyStr
