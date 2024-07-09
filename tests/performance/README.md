# performance testing using [locust.io](https://docs.locust.io/en/stable/index.html)

Locust allows simple testing of endpoints, and checks for response time, response type. It also allows to create useful reports.

## configuration

In the [locust_files] folder are located the test files.

## Usage

1. Generate a `.env` file with setting for your test. After running `make install-dev` you can execute your test script in python and set settings as arguments. Once your settings are validated you pipe them to `.env`, e.g.
```bash
python locust_files/platform_ping_test.py --LOCUST_HOST=https://api.osparc-master.speag.com  \
--LOCUST_USERS=100 --LOCUST_RUN_TIME=0:10:00 --SC_USER_NAME=myname --SC_PASSWORD=mypassword > .env
```
2. Run your test script using the Make `test` recipe, setting the correct `target`, e.g.
```
make test target=locust_files/platform_ping_test.py
```
