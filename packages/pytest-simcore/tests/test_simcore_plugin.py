# -*- coding: utf-8 -*-


def test_using_pytest_simcore_fixture(testdir):
    """Make sure that pytest accepts our fixture."""

    # create a temporary pytest test module
    testdir.makepyfile("""
        pytest_plugins = ["pytest_simcore.environs"]

        def test_sth(request):
            assert request.config.getoption("--keep-docker-up") == True
    """)

    # run pytest with the following cmd args
    result = testdir.runpytest(
        '--keep-docker-up',
        '-v'
    )

    # fnmatch_lines does an assertion internally
    # WARNING: this does not work with pytest-sugar!
    result.stdout.fnmatch_lines([
        '*::test_sth PASSED*',
    ])

    # make sure that that we get a '0' exit code for the testsuite
    assert result.ret == 0


def test_help_message(testdir):
    result = testdir.runpytest(
        '--help',
    )
    # fnmatch_lines does an assertion internally
    result.stdout.fnmatch_lines([
        'simcore:',
        '*--keep-docker-up*Keep stack/registry up after fixtures closes',
    ])


def test_hello_ini_setting(testdir):
    testdir.makeini("""
        [pytest]
        HELLO = world
    """)

    testdir.makepyfile("""
        import pytest

        @pytest.fixture
        def hello(request):
            return request.config.getini('HELLO')

        def test_hello_world(hello):
            assert hello == 'world'
    """)

    result = testdir.runpytest('-v')

    # fnmatch_lines does an assertion internally
    result.stdout.fnmatch_lines([
        '*::test_hello_world PASSED*',
    ])

    # make sure that that we get a '0' exit code for the testsuite
    assert result.ret == 0
