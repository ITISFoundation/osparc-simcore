from scheduler import main


def test_main_import(mocker):
    mocker.patch("uvicorn.run", return_value=True)
    assert main.main() is None
