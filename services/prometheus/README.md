# monitoring with [prometheus]


![](https://cdn.rawgit.com/prometheus/prometheus/e761f0d/documentation/images/architecture.svg)


- [servicelib](../../packages/service-library/src/servicelib/monitoring.py) inject the following metrics:
  - ``simcore_requests_total{app_name, method,endpoint, http_status}``


## localhost


- [osparc website](http://127.0.0.1:9081)
  - [osparc restAPI](http://127.0.0.1:9081/v0)
- [adminer website](http://127.0.0.1:18080): postgres database view
- [portainer](http://127.0.0.1:9000): swarm monitoring
- [prometheus website](http://127.0.0.1:9090): scraps metrics
  - [status targets](http://127.0.0.1:9090/targets)
- [graphana website](http://127.0.0.1:3000): dashboards to visualize metrics



```
http_requests_total{endpoint=~"/v0/.*"}
http_requests_total{endpoint=~"/v0/.*", http_status=~"2[0-9]+"}


```

[prometheus]:https://prometheus.io/docs
