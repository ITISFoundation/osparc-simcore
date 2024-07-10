# performance testing using [locust.io](https://docs.locust.io/en/stable/index.html)

Locust allows simple testing of endpoints, and checks for response time, response type. It also allows to create useful reports.

## configuration

In the [locust_files] folder are located the test files.

## Usage

1. All settings are passed to the locust container as environment variables in `.env`. To generate locust env vars, run `locust_settings.py` with appropriate settings and pipe it to `.env`:
```bash
python locust_settings.py --LOCUST_HOST=https://api.osparc-master.speag.com  \
--LOCUST_USERS=100 --LOCUST_RUN_TIME=0:10:00 > .env
```
2. Add settings related to your locust file. E.g. if your file expects to find an environment variable `MYENVVAR` you add it to `.env`:
```bash
echo "MYENVVAR=thisismyenvvar" >> .env
```
3. Once you have all settings setup you uun your test script using the Make `test` recipe:
```bash
make test
```

## Dashboards for visualization
- You can visualize the results of your tests (in real time) in a collection of beautiful [Grafana dashboards](https://github.com/SvenskaSpel/locust-plugins/tree/master/locust_plugins/dashboards).
- To do this, run `make dashboards-up` and go to `localhost:3000` to view the dashboards. The way you tell locust to send test results to the database/grafana is by ensuring `LOCUST_TIMESCALE=1` (see how to generate settings in [usage](#usage))
- When you are done you run `make dashboards-down` to clean up.
- If you are using VPN you will need to forward port 300 to your local machine to view the dashboard.


## Tricky settings 🚨
- `LOCUST_TIMESCALE` tells locust whether or not to send data to the database associated with visualizing the results. If you are not using the Grafana [dashboards](#dashboards-for-visualization) you should set `LOCUST_TIMESCALE=0`.
