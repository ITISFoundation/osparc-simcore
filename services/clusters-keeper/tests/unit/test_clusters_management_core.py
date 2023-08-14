# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


async def test_cluster_management_core_properly_unused_instances(
    disable_clusters_management_background_task: None,
    _base_configuration: None,
    clusters_keeper_rabbitmq_rpc_client: RabbitMQClient,
    ec2_client: EC2Client,
    user_id: UserID,
    wallet_id: WalletID,
):
    await _create_cluster(
        clusters_keeper_rabbitmq_rpc_client, ec2_client, user_id, wallet_id
    )
