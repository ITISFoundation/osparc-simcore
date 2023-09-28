#!/bin/bash


service_names=("webserver" "wb-db-event-listener" "wb-garbage-collector")


for service_name in "${service_names[@]}"
do
  name_filter="master-simcore_$service_name"
  echo "Containers with names '$name_filter':"
  containers=$(docker ps -a --filter "status=running" --filter "name=$name_filter" --format "{{.ID}}")

  for container_id in $containers
  do
      # Get the name of the container
      container_name=$(docker inspect -f '{{.Name}}' "$container_id" | cut -c 2-)

      # Execute the command in the container to create settings.json
      docker exec "$container_id" simcore-service-webserver settings --as-json > "${container_name}-settings.ignore.json"

  done
done
