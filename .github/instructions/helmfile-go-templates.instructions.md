---
applyTo: '**/*.yaml.gotmpl'
---

# Helmfile Go Templates instructions

## Reusing values

1. Avoid YAML anchors (`&name`, `*name`, `<<:`) Use
   Go template variables (`{{ $x := ... }}`) instead.
