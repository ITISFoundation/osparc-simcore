| service name    | defininition | implementation | runs                    | ``ServiceType``               |                 |
| --------------- | ------------ | -------------- | ----------------------- | ----------------------------- | --------------- |
| ``file-picker`` | BE           | FE             | FE                      | ``ServiceType.FRONTEND``      | function        |
| ``isolve``      | DI-labels    | DI             | Dask-BE (own container) | ``ServiceType.COMPUTATIONAL`` | container       |
| ``jupyter-*``   | DI-labels    | DI             | DySC-BE (own container) | ``ServiceType.DYNAMIC``       | container       |
| ``iterator-*``  | BE           | BE             | BE    (webserver)       | ``ServiceType.FRONTEND``      | function        |
| ``pyfun-*``     | BE           | BE             | Dask-BE  (dask-sidecar) | ``ServiceType.COMPUTATIONAL`` | function (TODO) |


where FE (front-end), DI (docker image), Dask/DySC (dask/dynamic sidecar), BE (backend).
