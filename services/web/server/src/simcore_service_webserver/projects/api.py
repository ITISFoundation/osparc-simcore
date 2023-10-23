# NOTE: we will slowly move heere projects_api.py


from ._permalink_api import ProjectPermalink
from ._permalink_api import register_factory as register_permalink_factory
from ._wallets_api import connect_wallet_to_project, get_project_wallet

__all__: tuple[str, ...] = (
    "register_permalink_factory",
    "ProjectPermalink",
    "get_project_wallet",
    "connect_wallet_to_project",
)


# nopycln: file
