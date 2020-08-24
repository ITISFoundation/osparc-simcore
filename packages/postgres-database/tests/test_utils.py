from yarl import URL

from simcore_postgres_database.utils import hide_dict_pass, hide_url_pass


def test_hide_url_pass():

    assert (
        hide_url_pass(URL("postgres://username:password@localhost/myrailsdb"))
        == "postgres://username:********@localhost/myrailsdb"
    )


def test_hide_dict_pass():

    assert hide_dict_pass({"pass": "foo", "password": "bar"}) == {
        "pass": "********",
        "password": "********",
    }
