from deploytools.merge import merge_docker_compose
from deploytools.readers import load_docker_compose


def test_merge_composes():

    main_compose = load_docker_compose()
    assert isinstance(main_compose, dict)

    devel_compose = load_docker_compose(".devel")
    assert isinstance(devel_compose, dict)


    tools_compose = load_docker_compose(".tools")
    assert isinstance(tools_compose, dict)


    merged = merge_docker_compose(main_compose, devel_compose, tools_compose)
    assert isinstance(merged, dict)

    assert "portainer" in merged["services"].keys()
    assert "portainer" not in devel_compose["services"].keys()
    assert "portainer" not in main_compose["services"].keys()
