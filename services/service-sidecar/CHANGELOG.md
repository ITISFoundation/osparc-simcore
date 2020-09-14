# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Planned]

- migrate to setup.py file
- add tests

## [Unreleased]

## [0.0.2] - 2020-07-15
### Added
- entry point to create containers without starting them
- entry point to stop running containers

### Modified
- moved more configurations to environment variables
- migrated to new project structure, after project was moved to osparc

## [0.0.1] - 2020-07-14
### Added
- FastAPI based service
- environs to manage configuration
- basic in memory storage , which can be easily extended for future needs
- async command execution of files
- context manger for to cleanup files after usage
- `docker-compose up` like entry point
- `docker-compose down` like entry point
- entry point to list docker-compose started container
- entry point to recover a container's logs
- entry point to inspect a container
- all spawned services and networks are removed when receiving `SIGTERM`
