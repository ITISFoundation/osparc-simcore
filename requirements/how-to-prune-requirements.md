
# Steps to prune a library and all services downstream


Libraries evolve and some of the dependencies are not anymore in use but remain listed in their requirements file. These are the steps to prune unused dependencies in a library and all services downstream.

For the sake of simplicity, let's assume we want to prune requirements of the library ``simcore-sdk`` (it should be analogous for any other package in the repository).


First we need to find which dependencies are not anymore used. For that we run [pipreqs](https://github.com/bndr/pipreqs) which will create a list of requirements that the target library is importing. Then, we can compare against the base requirements ``simcore-sdk/requirements/_base.in`` to figure out which have to be pruned from the list. Once the ``_base.in`` has been modified, we can full upgrade the requirements.


1. ``pip install pipreqs``
1. find dependencies in use: ``pipreqs packages/simcore-sdk/src/simcore_sdk`` produces a ``requirements.txt`` file
1. compare this file with ``packages/simcore-sdk/requirements/_base.in`` and remove unused libraries.
1. dependencies with other libraries in the repo under ``packages`` has to be reviewed manually
1. make full upgrade of reqs : ``make touch reqs``


At this point ``simcore-sdk``'s requirement are up-to-date. Now, we need to propagate the changes to the services and libraries that include this library. Notice that during this update, *we should not update any other dependencies other than those added by ``simcore-sdk``*.


6. Find packages that use the library : check for ``/packages/simcore-sdk/requirements/_base.in`` in all the repo including only ``*.in`` files:
  ```bash
  cd osparc-simcore
  grep --include=\*.in -rnw -e 'packages/simcore-sdk/requirements/_base.in' .
  ```
7. Go to those services ``requirements`` folder
1. We want to **selectively upgrade** the dependencies pulled by the upstream library in this service. We can do that by selective upgrade each of the libraries that ``simcore-sdk`` lists. Checking ``/packages/simcore-sdk/requirements/_base.in`` , we select e.g. ``aiohttp`` and proceed with a selective upgrade using our tooling:
```
make touch
make reqs upgrade=aiohttp
```
9. Check changes in the ``requirements`` folder. It should have only a partial upgrade



----

NOTE: An example can be found in PR [#2664](https://github.com/ITISFoundation/osparc-simcore/pull/2664)
