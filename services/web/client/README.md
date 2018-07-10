# web/client

``qxapp`` is the main client-side application of the sim-core platform.

To ease development of the client, we have encapsulated the [qx]-compiler and all setup needed to run the client in a container. This way, we can develop the
client without connecting to the final server but instead emulating it.

Due to **limitations of docker on a Windows** host, a workaround is needed to enabling watching [qx] source code. The [docker-windows-volume-watcher](https://github.com/merofeev/docker-windows-volume-watcher) tool will notify Docker containers about changes in mounts on Windows. For convenience we provide a script in ``osparc-simcore/scripts/win-watcher.bat``.


The docker-compose files in this directory help running ``qxapp`` stand-alone using a dev server in [qx].
```bash
cd path/to/web/client

# 1)build image
docker-compose build
# or
BUILD_TARGET=development docker-compose build
#    BUILD_TARGET variable sets the image target to ``development`` (default) or ``build``
#    and results in an image tagged accordingly `qx_client:$BUILD_TARGET1

# 2) check versions if programms installed inside
docker-compose run --rm qx --version

# 3) produce api doc
docker-compose run --rm qx api

# 4) produce test-runner with watch on source/ for test-drive development
docker-compose run --rm qx test-source

# 5) serves app, tests and doc in 8080, 8081 and 8082 resp.
# installs theme and fires qx serve. Open http://localhost:8080/index.html?qxenv:dev.enableFakeSrv:true
docker-compose up

```
Open then:

- source-output: http://localhost:8080
- test: http://localhost:8081/client/test/index-source.html
- api: http://localhost:8082

Finally, ``docker-compose down``. Once 1), 3) and 4) are performed once. The typical workflow would only consist of ``docker-compose down`` / ``down``


For a fake backend, open http://localhost:8080/index.html?qxenv:dev.enableFakeSrv:true otherwise http://localhost:8080/

## URL environmet variables

client's development container ``qx serve --set qx.allowUrlSettings=true`` and the following develompent settings are defined:

 - ``dev.enableFakeSrv: true/[false]`` : enables/disables fake server. Used exclusively for development.
 - ``dev.disableLogin:  true/[false]``  : enables/disables login page. Used exclusively for development.

 Examples:
  - http://localhost:8080/
  - http://localhost:8080/index.html?qxenv:dev.enableFakeSrv:true
  - http://localhost:8080/index.html?qxenv:dev.enableFakeSrv:true&qxenv:dev.disableLogin:true

## Build/Run Services

This project uses a multi-stage ``Dockerfile`` that targets images for *development*
and *production*, respectively. In this context, a *development* container mounts
``client`` folder and reacts to source code changes. On the the hand, the
*production* container copies ``client`` folder inside instead. The latter is intended as a intermediate stage for the ``web/server`` container. This is how the ``Dockerfile`` is split:

[![service-web](docs/img/dockerfile.svg)](http://interactive.blockdiag.com/image?compression=deflate&encoding=base64&src=eJx9kMFuwyAMhu99Cot79gJRd-h5h92rHkhiJSgupkCiVlPfvQYyiU5rkUDYv_g__3TE_TwYPcLPDkChjf7m2Nj4ESYFxzBph3vLEU9JvlwhoF_xj7KD0fPisgXpDgn2oDodsAlRj6ha6UPaYtD0fHaG0Ks2l2GYlUj32gMqG-d5WPpo2BYbWT0T-6R9mXGK38bOIm2aMlaYRIKRKKZLMTIINu5WlRjp0UvygCsSu7P8yQv0gRas0M-fV7zlrDJD8wklc7r9N2vuV9P-1mXe9q3dMz_PdX8APQWRAQ)

In order to build/run each target image, we override ``docker-compose`` configuration files: ``docker-compose.yml`` and ``docker-compose.production.yml``

open a new console, and type this to stop
``` bash
cd path/to/web/client
docker-compose down
```
### Limitiations running in a Windows host

**Development version of image doesn't work on a windows host**. Modified files in the mounted volume don't trigger container operating  system notifications, so watchers don't react to changes. This is a known limitation of docker on windows. A [workaround](http://blog.subjectify.us/miscellaneous/2017/04/24/docker-for-windows-watch-bindings.html) is possible. Open terminal in windows host and type:

```bash
pip install docker-windows-volume-watcher
docker-volume-watcher
```

**NOTE** Use scripts in ``osparc-simcore/scripts/win-watcher.bat``





[qx]:http://www.qooxdoo.org/
