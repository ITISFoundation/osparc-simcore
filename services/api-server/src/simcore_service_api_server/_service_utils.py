from typing import Protocol

from models_library.products import ProductName
from models_library.users import UserID

from .exceptions.custom_errors import ServiceConfigurationError


class UserProductProvider(Protocol):
    """Protocol for classes that provide user_id and product_name properties."""

    @property
    def user_id(self) -> UserID: ...

    @property
    def product_name(self) -> ProductName: ...


def check_user_product_consistency(
    service_cls_name: str,
    service_provider: UserProductProvider,
    user_id: UserID,
    product_name: ProductName,
) -> None:

    if user_id != service_provider.user_id:
        msg = f"User ID {user_id} does not match {service_provider.__class__.__name__} user ID {service_provider.user_id}"
        raise ServiceConfigurationError(
            service_cls_name=service_cls_name, detail_msg=msg
        )
    if product_name != service_provider.product_name:
        msg = f"Product name {product_name} does not match {service_provider.__class__.__name__}product name {service_provider.product_name}"
        raise ServiceConfigurationError(
            service_cls_name=service_cls_name, detail_msg=msg
        )
