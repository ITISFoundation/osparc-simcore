import dask_gateway

auth = dask_gateway.BasicAuth(username="mytester", password="qweqwe")


async def test_it():
    async with dask_gateway.Gateway(
        "http://127.0.0.1:50001", auth=auth, asynchronous=True
    ) as gateway:
        print(f"--> created {gateway=}")

        cluster_options = await gateway.cluster_options()
        gateway_versions = await gateway.get_versions()
        clusters_list = await gateway.list_clusters()
        print(f"--> {gateway_versions=}, {cluster_options=}, {clusters_list=}")
        for option in cluster_options.items():
            print(f"--> {option=}")

        async with gateway.new_cluster() as cluster:
            assert cluster
            print(f"--> created new cluster {cluster=}, {cluster.scheduler_info=}")
            await cluster.adapt()
            async with cluster.get_client() as client:
                print(f"--> created new client {client=}")
                print(f"--> client scheduler has {client.scheduler_info()=}")
                print(f"--> cluster scheduler has {cluster.scheduler_info=}")
                res = await client.submit(lambda x: x + 1, 1)  # type: ignore
                assert res == 2
                print("---------AFTER SUBMITTING----------")
                print(f"--> cluster scheduler has {cluster.scheduler_info=}")
                print(f"--> client scheduler has {client.scheduler_info()=}")
