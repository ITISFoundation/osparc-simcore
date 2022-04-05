from contextlib import suppress
from typing import Any, Dict, Type, cast

import pytest
from models_library.clusters import BaseCluster, Cluster
from pydantic import BaseModel
from simcore_service_director_v2.utils.db import to_clusters_db


@pytest.mark.parametrize(
    "model_cls",
    (Cluster,),
)
def test_export_clusters_to_db(
    model_cls: Type[BaseModel], model_cls_examples: Dict[str, Dict[str, Any]]
):
    for example in model_cls_examples.values():
        owner_gid = example["owner"]
        # remove the owner from the access rights if any
        with suppress(KeyError):
            example.get("access_rights", {}).pop(owner_gid)
        instance = cast(BaseCluster, model_cls(**example))

        # for updates

        cluster_db_dict = to_clusters_db(instance, only_update=True)
        keys_not_in_db = ["id", "access_rights"]

        assert list(cluster_db_dict.keys()) == [
            x for x in example if x not in keys_not_in_db
        ]
