from simcore_postgres_database.models.users import _USER_ROLE_TO_LEVEL, UserRole


def test_user_role_to_level_map_in_sync():
    # If fails, then update _USER_ROLE_TO_LEVEL map
    assert set(_USER_ROLE_TO_LEVEL.keys()) == set(UserRole.__members__.keys())


def test_user_role_comparison():

    assert UserRole.ANONYMOUS < UserRole.ADMIN
    assert UserRole.GUEST < UserRole.ADMIN
    assert UserRole.USER < UserRole.ADMIN
    assert UserRole.TESTER < UserRole.ADMIN
    assert UserRole.ADMIN == UserRole.ADMIN

    assert UserRole.ANONYMOUS < UserRole.TESTER
    assert UserRole.GUEST < UserRole.TESTER
    assert UserRole.USER < UserRole.TESTER
    assert UserRole.TESTER == UserRole.TESTER
    assert UserRole.ADMIN > UserRole.TESTER

    assert UserRole.ANONYMOUS < UserRole.USER
    assert UserRole.GUEST < UserRole.USER
    assert UserRole.USER == UserRole.USER
    assert UserRole.TESTER > UserRole.USER
    assert UserRole.ADMIN > UserRole.USER

    assert UserRole.ANONYMOUS < UserRole.GUEST
    assert UserRole.GUEST == UserRole.GUEST
    assert UserRole.USER > UserRole.GUEST
    assert UserRole.TESTER > UserRole.GUEST
    assert UserRole.ADMIN > UserRole.GUEST

    assert UserRole.ANONYMOUS == UserRole.ANONYMOUS
    assert UserRole.GUEST > UserRole.ANONYMOUS
    assert UserRole.USER > UserRole.ANONYMOUS
    assert UserRole.TESTER > UserRole.ANONYMOUS
    assert UserRole.ADMIN > UserRole.ANONYMOUS

    # < and >
    assert UserRole.TESTER < UserRole.ADMIN
    assert UserRole.ADMIN > UserRole.TESTER

    # >=, == and <=
    assert UserRole.TESTER <= UserRole.ADMIN
    assert UserRole.ADMIN >= UserRole.TESTER

    assert UserRole.ADMIN <= UserRole.ADMIN
    assert UserRole.ADMIN == UserRole.ADMIN
