from contextlib import suppress
from typing import Any, cast

import pytest
from models_library.clusters import BaseCluster, Cluster
from models_library.projects_state import RunningState
from pydantic import BaseModel
from simcore_postgres_database.models.comp_pipeline import StateType
from simcore_service_director_v2.utils.db import (
    DB_TO_RUNNING_STATE,
    RUNNING_STATE_TO_DB,
    to_clusters_db,
)


@pytest.mark.parametrize(
    "model_cls",
    [Cluster],
)
def test_export_clusters_to_db(
    model_cls: type[BaseModel], model_cls_examples: dict[str, dict[str, Any]]
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


@pytest.mark.parametrize("input_running_state", RunningState)
def test_running_state_to_db(input_running_state: RunningState):
    assert input_running_state in RUNNING_STATE_TO_DB


@pytest.mark.parametrize("input_state_type", StateType)
def test_db_to_running_state(input_state_type: StateType):
    assert input_state_type in DB_TO_RUNNING_STATE
