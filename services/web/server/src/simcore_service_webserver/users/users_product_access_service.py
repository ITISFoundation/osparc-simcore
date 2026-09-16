# NOTE: This is a separate public surface instead of a re-export through the primary
# `users_service` facade to avoid a cyclic import. The aggregation module imports
# `groups_service`, which itself imports `users_service`; re-exporting
# `grant_user_access_to_product` from `users_service` would close a
# `users <-> groups` import cycle.
# See services/web/server/docs/DESIGN.md -> "Preventing Cyclic Imports" and
# "Public Facade Rules" (secondary public surfaces).
from ._grant_product_access_aggregation_service import grant_user_access_to_product

__all__: tuple[str, ...] = ("grant_user_access_to_product",)  # nopycln: file
