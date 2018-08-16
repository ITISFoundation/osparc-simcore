#!/bin/sh
curl localhost:8001

curl localhost:8001/list_interactive_services

curl localhost:8001/list_interactive_services

curl \
  --header "Content-Type: application/json" \
  --request POST \
  --data '{"service_name":"jupyter-base-notebook", "service_uuid":"1234"}' \
  localhost:8001/start_service
