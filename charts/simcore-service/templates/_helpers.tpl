{{- define "simcore-service.name" -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "simcore-service.envSecretName" -}}
{{- printf "%s-env" (include "simcore-service.name" . | trunc 58 | trimSuffix "-") -}}
{{- end -}}

{{- define "simcore-service.labels" -}}
app.kubernetes.io/name: {{ include "simcore-service.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
{{- end -}}

{{- /*
Map entries (valueFrom) are rendered before plain values: Kubernetes expands
$(VAR) only from entries earlier in the list, and range sorts map keys.
*/ -}}
{{- define "simcore-service.containerEnv" -}}
{{- range $name, $v := .Values.env }}
{{- if kindIs "map" $v }}
- name: {{ $name }}
  {{- toYaml $v | nindent 2 }}
{{- end }}
{{- end }}
{{- range $name, $v := .Values.env }}
{{- if not (or (kindIs "invalid" $v) (kindIs "map" $v)) }}
- name: {{ $name }}
  value: {{ $v | toString | quote }}
{{- end }}
{{- end }}
{{- end -}}
