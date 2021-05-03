# comp-resource-manager

Platform's computational resource manager


## Development

Setup environment

```console
make devenv
source .venv/bin/activate
cd services/comp-resource-manager
make install-dev
```

Then

```console
make run-devel
```

will start the comp-resource-manager in development-mode together with a postgres db initialized with test data. Open the following sites and use the test credentials ``user=key, password=secret`` to manually test the API:

- http://127.0.0.1:8000/docs: redoc documentation
- http://127.0.0.1:8000/dev/docs: swagger type of documentation

## References

- [Design patterns for modern web APIs](https://blog.feathersjs.com/design-patterns-for-modern-web-apis-1f046635215) by D. Luecke
- [API Design Guide](https://cloud.google.com/apis/design/) by Google Cloud

## Acknoledgments

  Many of the ideas in this design were taken from the **excellent** work at https://github.com/nsidnev/fastapi-realworld-example-app by *Nik Sidnev* using the **extraordinary** [fastapi](https://fastapi.tiangolo.com/) package by *Sebastian Ramirez*.
