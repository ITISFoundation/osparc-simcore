from pydantic import BaseModel

from models_library.projects_nodes_io import NodeID
from models_library.wallets import WalletID


class ServiceNoMoreCredits(BaseModel):
    node_id: NodeID
    wallet_id: WalletID
