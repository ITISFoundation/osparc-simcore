---
applyTo: '**/*.yaml.gotmpl'
---

# Helmfile Go Templates instructions

## Reusing values

* Avoid YAML anchors (`&name`, `*name`, `<<:`) Use
   Go template variables (`{{ $x := ... }}`) instead.
* Use `.Release.Name` and `.Release.Namespace` and other
  available helmfile variables instead of hardcoding values.

## Referring to env

* Use `requiredEnv "X"` to refer to required environment variables.
* Use `env "X" | default "..."` to refer to optional environment variables.

## Formatting

* Emit strings with `| quote`. Use `| squote` for regex paths containing `\`.
* Trim whitespace with `{{-` so the YAML indentation stays intact.
