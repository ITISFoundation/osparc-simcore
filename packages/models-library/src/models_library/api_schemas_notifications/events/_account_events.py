from typing import Any, Literal

from pydantic import BaseModel, EmailStr, HttpUrl

from models_library.products import ProductName


class UserData(BaseModel):
    username: str
    first_name: str
    last_name: str
    email: EmailStr


class ProductUIData(BaseModel):
    project_alias: str
    logo_url: HttpUrl | None = None
    strong_color: str | None = None


class ProductData(BaseModel):
    product_name: ProductName
    display_name: str
    vendor_display_inline: str
    support_email: EmailStr
    homepage_url: HttpUrl | None
    ui: ProductUIData


class BaseAccountEvent(BaseModel):
    user: UserData
    product: ProductData


class AccountRequestedEvent(BaseAccountEvent):
    type: Literal["account_requested"] = "account_requested"

    host: str

    # NOTE: following are kept for backward compatibility
    product_info: dict[str, Any] = {}
    request_form: dict[str, Any] = {}
    ipinfo: dict[str, Any] = {}


class AccountApprovedEvent(BaseAccountEvent):
    type: Literal["account_approved"] = "account_approved"

    link: HttpUrl


class AccountRejectedEvent(BaseAccountEvent):
    type: Literal["account_rejected"] = "account_rejected"

    reason: str
