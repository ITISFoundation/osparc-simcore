#!/bin/bash

# Enable that for debug
#set -x

# The command piped into the while loop is a list of all docker container names we want to inspect.

while read -r line; do
    ################
	# TEST TO CHECK FOR CI DEPLOY FAILURE
	# OBSERVED FIRST ON 01Dec2021
	# Get the short commit sha (first 6 alphanumericals, as common in git)
	export line=$(echo "$line" | tr -d '"' | tr -d ',')
	export COMMIT_TAG_SEARCH_STRING=$(docker image inspect ${line} | jq '.[0].Config.Labels."org.label-schema.vcs-ref"')
	export COMMIT_TAG_SEARCH_STRING=$(echo "$COMMIT_TAG_SEARCH_STRING" | tr -d '"')
	# Get the full sha hash from container name
	export FULL_DOCKER_IMAGE_NAME=$(docker image inspect ${line} | jq '.[0]."RepoTags" | join(",")')
	echo "COMMIT_TAG_SEARCH_STRING:"
	echo $COMMIT_TAG_SEARCH_STRING
	echo "FULL_DOCKER_IMAGE_NAME:"
	echo $FULL_DOCKER_IMAGE_NAME
	# Check if they match
	# Find substring in string via https://stackoverflow.com/questions/17203122/bash-if-else-statement-in-one-line/17203203
	if [[ "$FULL_DOCKER_IMAGE_NAME" == *"$COMMIT_TAG_SEARCH_STRING"* ]];
	then
	echo "Sanity Check succeeded: Found expected commit hash in container name";
	else
	echo 'Sanity Check failed: Commit-SHA from container name and short sha hash found in Containder Config.Labels."org.label-schema.vcs-ref" NOT MATCHING' && \
	echo 'This means the containter does not match the expected git commit.';
	exit 1;
fi
done <<< "$(make info-images 2>/dev/null | grep itisfoundation | grep -v ago | grep -v Error | grep -v "\#" | grep $DOCKER_IMAGE_TAG)"
#exit 0;
