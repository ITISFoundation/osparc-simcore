# performance testing using [locust.io](https://docs.locust.io/en/stable/index.html)

Locust allows simple testing of endpoints, and checks for response time, response type. It also allows to create useful reports.

## configuration

In the [locust_files] folder are located the test files.

## Usage

1. All settings are passed to the locust container as environment variables in `.env`. To generate locust env vars, run `make config` with appropriate `input`. To see what the possible settings are, run `make config input="--help"`. E.g. you could run
```bash
make config input="--LOCUST_HOST=https://api.osparc-master.speag.com
--LOCUST_USERS=100 --LOCUST_RUN_TIME=0:10:00 --LOCUST_LOCUSTFILE=locust_files/platform_ping_test.py"
```
This will validate your settings and you should be good to go once you see a the settings printed in your terminal.

2. Once you have all settings setup you run your test script using the Make `test` recipe:
```bash
make test-up
```

3. If you want to clean up after your tests (remove docker containers) you run `make test-down`

## Dashboards for visualization
- You can visualize the results of your tests (in real time) in a collection of beautiful [Grafana dashboards](https://github.com/SvenskaSpel/locust-plugins/tree/master/locust_plugins/dashboards).
- To do this, run `make dashboards-up`. If you are on linux you should see your browser opening `localhost:3000`, where you can view the dashboards. If the browser doesn't open automatically, do it manually and navigate to `localhost:3000`.The way you tell locust to send test results to the database/grafana is by ensuring `LOCUST_TIMESCALE=1` (see how to generate settings in [usage](#usage))
- When you are done you run `make dashboards-down` to clean up.
- If you are using VPN you will need to forward port 3000 to your local machine to view the dashboard.


## Tricky settings 🚨
- `LOCUST_TIMESCALE` tells locust whether or not to send data to the database associated with visualizing the results. If you are not using the Grafana [dashboards](#dashboards-for-visualization) you should set `LOCUST_TIMESCALE=0`.
