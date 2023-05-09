from pytest_simcore.helpers.utils_docker import ContainerStatus


def test_it():

    # save_docker_infos("ignore.test_it")
    assert "created" == ContainerStatus.CREATED
