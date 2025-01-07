# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from common_library.users_enums import _USER_ROLE_TO_LEVEL, UserRole


def test_user_role_to_level_map_in_sync():
    # If fails, then update _USER_ROLE_TO_LEVEL map
    assert set(_USER_ROLE_TO_LEVEL.keys()) == set(UserRole.__members__.keys())


def test_user_roles_compares_to_admin():
    assert UserRole.ANONYMOUS < UserRole.ADMIN
    assert UserRole.GUEST < UserRole.ADMIN
    assert UserRole.USER < UserRole.ADMIN
    assert UserRole.TESTER < UserRole.ADMIN
    assert UserRole.PRODUCT_OWNER < UserRole.ADMIN
    assert UserRole.ADMIN == UserRole.ADMIN


def test_user_roles_compares_to_product_owner():
    assert UserRole.ANONYMOUS < UserRole.PRODUCT_OWNER
    assert UserRole.GUEST < UserRole.PRODUCT_OWNER
    assert UserRole.USER < UserRole.PRODUCT_OWNER
    assert UserRole.TESTER < UserRole.PRODUCT_OWNER
    assert UserRole.PRODUCT_OWNER == UserRole.PRODUCT_OWNER
    assert UserRole.ADMIN > UserRole.PRODUCT_OWNER


def test_user_roles_compares_to_tester():
    assert UserRole.ANONYMOUS < UserRole.TESTER
    assert UserRole.GUEST < UserRole.TESTER
    assert UserRole.USER < UserRole.TESTER
    assert UserRole.TESTER == UserRole.TESTER
    assert UserRole.PRODUCT_OWNER > UserRole.TESTER
    assert UserRole.ADMIN > UserRole.TESTER


def test_user_roles_compares_to_user():
    assert UserRole.ANONYMOUS < UserRole.USER
    assert UserRole.GUEST < UserRole.USER
    assert UserRole.USER == UserRole.USER
    assert UserRole.TESTER > UserRole.USER
    assert UserRole.PRODUCT_OWNER > UserRole.USER
    assert UserRole.ADMIN > UserRole.USER


def test_user_roles_compares_to_guest():
    assert UserRole.ANONYMOUS < UserRole.GUEST
    assert UserRole.GUEST == UserRole.GUEST
    assert UserRole.USER > UserRole.GUEST
    assert UserRole.TESTER > UserRole.GUEST
    assert UserRole.PRODUCT_OWNER > UserRole.GUEST
    assert UserRole.ADMIN > UserRole.GUEST


def test_user_roles_compares_to_anonymous():
    assert UserRole.ANONYMOUS == UserRole.ANONYMOUS
    assert UserRole.GUEST > UserRole.ANONYMOUS
    assert UserRole.USER > UserRole.ANONYMOUS
    assert UserRole.TESTER > UserRole.ANONYMOUS
    assert UserRole.PRODUCT_OWNER > UserRole.ANONYMOUS
    assert UserRole.ADMIN > UserRole.ANONYMOUS


def test_user_roles_compares():
    # < and >
    assert UserRole.TESTER < UserRole.ADMIN
    assert UserRole.ADMIN > UserRole.TESTER

    # >=, == and <=
    assert UserRole.TESTER <= UserRole.ADMIN
    assert UserRole.ADMIN >= UserRole.TESTER

    assert UserRole.ADMIN <= UserRole.ADMIN
    assert UserRole.ADMIN == UserRole.ADMIN
