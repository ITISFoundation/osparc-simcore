# web/client

``qxapp`` is the main client-side application of the sim-core platform.

## Development

To ease development of the client, we have encapsulated the [qx]-compiler and all setup needed to run the client in a contiainer. This way, we can develop the
client without connecting to the final server but instead emulating it.

The docker-compose files in this directory help running ``qxapp`` stand-alone using a dev server in [qx]. This is a common workflow:

```bash
cd /.../web/client

# 1. the first time you checkout, you need to pull qx contribution packages
docker-compose -f docker-compose.yml -f ./docker/docker-compose.init.yml run qx

# 2. runs 'qx serve' which serves a website in http://localhost:8080/.
#    Changes in your code will automatically be compiled and updated in the web.
docker-compose up

# 3. close down
docker-compose down
```

To access [qx]-compiler CLI simply type ```docker-compose run qx [qx commands/options]```. Some examples:

```bash

docker-compose run qx --help

# compiles code and recompiles as sources changes
docker-compose run qx compile --watch

docker-compose run qx lint

docker-compose run qx clean

# removes all containers created previously
docker-compose down
```

[qx]:http://www.qooxdoo.org/
