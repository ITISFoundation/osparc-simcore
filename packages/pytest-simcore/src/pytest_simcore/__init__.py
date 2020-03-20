# Collection of tests fixtures for integration testing

def pytest_addoption(parser):
    group = parser.getgroup("simcore")
    group.addoption(
        "--keep-docker-up",
        action="store_true",
        default=False,
        help="Keep stack/registry up after fixtures closes",
    )

    # DUMMY
    parser.addini('HELLO', 'Dummy pytest.ini setting')
