from typing import Any, Dict


def test_sidecar_service_is_deployed_in_global_mode(
    simcore_docker_compose: Dict[str, Any]
):
    dask_sidecar_deploy_config = simcore_docker_compose["services"]["dask-sidecar"][
        "deploy"
    ]
    assert dask_sidecar_deploy_config["mode"] == "global"
