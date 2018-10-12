#!/bin/bash
docker rmi $(docker images -q) -f