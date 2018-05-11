# web/server

Corresponds to the ```webserver``` service

## Development

Build images of ```webserver```

### Debug

```bash
  cd /path/to/simcore/services

  # development image: image gets labeled as services_webserver:dev
  docker-compose -f docker-compose.yml -f docker-compose.debug.yml build webserver
```

### Release

```bash
  cd /path/to/simcore/services

  # production image: image gets labeled as services_webserver:latest
  docker-compose -f docker-compose.yml build webserver
```
