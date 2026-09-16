"""Aggregated "grant product access" sequence shared by every code path that
confirms a user into a product (self-registration, pre-registration approval, ...)

Keeping the whole sequence in a single place prevents the paths from drifting
apart (e.g. one of them forgetting to emit SIGNAL_ON_USER_CONFIRMATION).
"""

from aiohttp import web
from models_library.products import ProductName
from models_library.users import UserID
from pydantic import PositiveInt
from servicelib.aiohttp import observer

from ..groups import groups_service

_SIGNAL_ON_USER_CONFIRMATION: str = "SIGNAL_ON_USER_CONFIRMATION"


async def grant_user_access_to_product(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    extra_credits_in_usd: PositiveInt | None = None,
) -> None:
    """Grants `user_id` access to `product_name` and notifies observers

    The emitted SIGNAL_ON_USER_CONFIRMATION marks that `user_id` was confirmed
    in `product_name` for the first time. The sequence is idempotent: group
    memberships are inserted with ON CONFLICT DO NOTHING and observers (e.g.
    default-wallet creation) are expected to be idempotent as well.

    NOTE: Follow up in https://github.com/ITISFoundation/osparc-simcore/issues/4822
    """
    await groups_service.auto_add_user_to_groups(app, user_id)

    await groups_service.auto_add_user_to_product_group(app, user_id=user_id, product_name=product_name)

    await observer.emit(
        app,
        _SIGNAL_ON_USER_CONFIRMATION,
        user_id=user_id,
        product_name=product_name,
        extra_credits_in_usd=extra_credits_in_usd,
    )
