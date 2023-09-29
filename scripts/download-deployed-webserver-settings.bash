#!/bin/bash

# all containers running on the image `local/webserver:production`
containers=$(docker ps -a --filter "status=running" --filter "ancestor=local/webserver:production" --format "{{.ID}}")

for container_id in $containers
do
    # Get the name of the container
    container_name=$(docker inspect -f '{{.Name}}' "$container_id" | cut -c 2-)

    # Execute the command in the container to create settings.json
    docker exec "$container_id" simcore-service-webserver settings --as-json > "${container_name}-settings.ignore.json"

done
