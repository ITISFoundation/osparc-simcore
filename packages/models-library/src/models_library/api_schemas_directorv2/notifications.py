from models_library.projects_nodes_io import NodeID
from models_library.wallets import WalletID
from pydantic.v1 import BaseModel


class ServiceNoMoreCredits(BaseModel):
    node_id: NodeID
    wallet_id: WalletID
