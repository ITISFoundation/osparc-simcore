from pathlib import Path

from faker import Faker
from fastapi import FastAPI
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.efs_guardian import efs_manager
from simcore_service_efs_guardian.core.settings import AwsEfsSettings

pytest_simcore_core_services_selection = ["rabbit"]
pytest_simcore_ops_services_selection = []


async def test_rpc_pricing_plans_workflow(
    rpc_client: RabbitMQRPCClient,
    faker: Faker,
    app: FastAPI,
):
    aws_efs_settings: AwsEfsSettings = app.state.settings.EFS_GUARDIAN_AWS_EFS_SETTINGS

    _project_id = faker.uuid4()
    _node_id = faker.uuid4()

    result = await efs_manager.create_project_specific_data_dir(
        rpc_client, project_id=_project_id, node_id=_node_id
    )
    assert isinstance(result, Path)
    _expected_path = (
        Path(aws_efs_settings.EFS_MOUNTED_PATH)
        / aws_efs_settings.EFS_PROJECT_SPECIFIC_DATA_DIRECTORY
        / _project_id
        / _node_id
    )
    assert _expected_path == result
    assert _expected_path.exists
