# static-webserver/client

This is the front-end (client-side) application of the osparc-simcore platform.

This application is written using [qooxdoo] and the [source](source) needs to be compiled before being served by the [webserver](../web/server).


## [qooxdoo] compiler

All [qooxdoo] tools used to compile this source code are pre-installed in the [itisfoundation/qooxdoo-kit](https://github.com/ITISFoundation/dockerfiles/tree/master/qooxdoo-kit) docker image. This toolkit is configured for this project in [tools](services/static-webserver/client/tools).

A **makefile** provides recipies to easily compile and *statically* serve the client application. The latter is mostly for development purposes.

    $ make help

The [itisfoundation/qooxdoo-kit] is used in two different ways:

- runs **as a container**, binds the current directly and compiles the code at **run-time**
- used **as a base image** of a [Dockerfile](services/static-webserver/client/tools/qooxdoo-kit/builder/Dockerfile) that compiles the source code at **build-time**.

The former is used in development and the latter is used for production. Some (hopefully) self-explanatory examples:

    $ make compile-dev flags=--watch

    $ make compile
    $ docker image ls | grep tools/qooxdoo-kit/compile*



> See **limitations of docker on a Windows** below (Sept. 2019)


## [qooxdoo] server

[qooxdoo] also comes with a *static* server that can be handy to view the UI when the interaction with the webserver backend is not necessary:

    $ make serve-dev

    $ make serve

The site is served in

- http://127.0.0.1:8080/
- http://127.0.0.1:8080/index.html?qxenv:dev.enableFakeSrv:true
- http://127.0.0.1:8080/index.html?qxenv:dev.enableFakeSrv:true&qxenv:dev.disableLogin:true
where
- ``dev.enableFakeSrv: true/[false]`` : enables/disables fake server. Used exclusively for development.
- ``dev.disableLogin:  true/[false]``  : enables/disables login page. Used exclusively for development.

For demo purposes, the user/pass to login when the fake server is active is ```bizzy@itis.ethz.ch``` and ```z43```, respectively.

## Frontend UI Workflow

![Frontend UI Workflow](docs/img/frontend-diagram.svg)

---

### Limitiations running in a Windows host

**Development version of image doesn't work on a windows host**. Modified files in the mounted volume don't trigger container operating  system notifications, so watchers don't react to changes. This is a known limitation of docker on windows. A [workaround](http://blog.subjectify.us/miscellaneous/2017/04/24/docker-for-windows-watch-bindings.html) is possible. Open terminal in windows host and type:

```bash
pip install docker-windows-volume-watcher
docker-volume-watcher
```

**NOTE** Use scripts in [osparc-simcore/scripts/win-watcher.bat](../../../scripts/win-watcher.bat)


<!-- ADD REFERENCES ALPHABETICALLY BELOW THIS LINE -->
[qooxdoo]:http://www.qooxdoo.org/
[itisfoundation/qooxdoo-kit]:https://github.com/ITISFoundation/dockerfiles/tree/master/qooxdoo-kit
