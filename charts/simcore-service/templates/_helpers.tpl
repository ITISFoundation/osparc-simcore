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

{{- define "simcore-service.containerEnv" -}}
{{- range .Values.env }}
- name: {{ .name }}
  {{- if .sensitive }}
  valueFrom:
    secretKeyRef:
      name: {{ include "simcore-service.envSecretName" $ }}
      key: {{ .name }}
  {{- else }}
  {{- if ne .value nil }}
  value: {{ .value | quote }}
  {{- else }}
  value: ""
  {{- end }}
  {{- end }}
{{- end }}
{{- end -}}
