.DEFAULT_GOAL := list-versions

SHELL := /bin/bash

list-versions:
	docker build -t docker-services-apt-versions:latest .
	docker run -it --rm docker-services-apt-versions:latest
