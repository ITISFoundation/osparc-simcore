# monitoring with [prometheus]


![](https://cdn.rawgit.com/prometheus/prometheus/e761f0d/documentation/images/architecture.svg)


- [servicelib](../../packages/service-library/src/servicelib/monitoring.py) inject the following metrics:
  - ``simcore_requests_total{app_name, method,endpoint, http_status}``

---
## localhost dashboard

- [osparc website](http://127.0.0.1:9081)
  - [restAPI](http://127.0.0.1:9081/v0) entrypoint
  - [metrics](http://127.0.0.1:9081/metrics) entrypoint
- [adminer website](http://127.0.0.1:18080): postgres database view
- [portainer](http://127.0.0.1:9000): swarm monitoring
- [maintenance service](http://127.0.0.1:9010): maintenance service
- [prometheus website](http://127.0.0.1:9090): scraps metrics
  - [status targets](http://127.0.0.1:9090/targets): shows status of monitored uservices (check ``/metrics`` to make sure scrabbing all metrics)
- [graphana website](http://127.0.0.1:3000): dashboards to visualize metrics


#### [PromQL] queries:

```
http_requests_total{endpoint=~"/v0/.*"}
http_requests_total{endpoint=~"/v0/.*", http_status=~"2[0-9]+"}
pg_stat_activity_count{datname="simcoredb", state=~"active|idle"}

```
---

[PromQL](https://prometheus.io/docs/prometheus/latest/querying/basics/
[prometheus]:https://prometheus.io/docs
