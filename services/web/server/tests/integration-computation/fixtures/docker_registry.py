import docker
import pytest
import tenacity


@pytest.fixture(scope="session")
def docker_registry(docker_stack):
    cfg = docker_stack
    # import pdb; pdb.set_trace()
    host = "127.0.0.1" #cfg["services"]["director"]["environment"]["REGISTRY_URL"]
    port = cfg["services"]["registry"]["ports"][0]["published"]
    url = "{host}:{port}".format(host=host, port=port)
    # Wait until we can connect
    assert _wait_till_registry_is_responsive(url)

    # test the registry
    docker_client = docker.from_env()
    # get the hello world example from docker hub
    hello_world_image = docker_client.images.pull("hello-world","latest")
    # login to private registry
    docker_client.login(registry=url, username=cfg["services"]["director"]["environment"]["REGISTRY_USER"])
    # tag the image
    repo = url + "/hello-world:dev"
    assert hello_world_image.tag(repo) == True
    # push the image to the private registry
    docker_client.images.push(repo)
    # wipe the images
    docker_client.images.remove(image="hello-world:latest")
    docker_client.images.remove(image=hello_world_image.id)
    # pull the image from the private registry
    private_image = docker_client.images.pull(repo)
    docker_client.images.remove(image=private_image.id)

    yield url

@tenacity.retry(wait=tenacity.wait_fixed(0.1), stop=tenacity.stop_after_delay(60))
def _wait_till_registry_is_responsive(url):
    try:
        docker_client = docker.from_env()
        docker_client.login(registry=url, username="test")
    except docker.errors.APIError:
        return False
    return True

#pull from itisfoundation/sleeper and push into local registry
@pytest.fixture(scope="session")
def sleeper_service(docker_registry):
    client = docker.from_env()
    image = client.images.pull("itisfoundation/sleeper", tag="1.0.0")
    assert not image is None
    repo = "{}/simcore/services/comp/itis/sleeper:1.0.0".format(docker_registry)
    assert image.tag(repo) == True
    client.images.push(repo)
    yield repo