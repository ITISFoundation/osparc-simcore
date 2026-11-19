---
applyTo: 'charts/simcore-service/**'
---

# Simcore chart instructions

- Changes in `templates/` must be tested/covered in `tests/*_test.yaml`
- Changes in `values.yaml` must be reflected in `values.schema.json`
- Validate with `make -C k8s helm-unittest`, `make -C k8s helmfile-lint` and
  `make -C k8s helmfile-template`
