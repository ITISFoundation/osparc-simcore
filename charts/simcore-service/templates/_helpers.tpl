{{- define "simcore-service.name" -}}
{{- .Release.Name -}}
{{- end -}}

{{- define "simcore-service.envSecretName" -}}
{{- printf "%s-env" (include "simcore-service.name" . | trimSuffix "-") -}}
{{- end -}}

{{- define "simcore-service.kind" -}}
{{- $kinds := list "Deployment" "DaemonSet" -}}
{{- if not (has .Values.kind $kinds) -}}
{{- fail (printf "kind must be one of %v, got %q" $kinds .Values.kind) -}}
{{- end -}}
{{- .Values.kind -}}
{{- end -}}

{{- define "simcore-service.selectorLabels" -}}
app.kubernetes.io/name: {{ include "simcore-service.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
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

{{- define "simcore-service.podTemplate" -}}
metadata:
  labels:
    {{- include "simcore-service.labels" . | nindent 4 }}
  annotations:
    checksum/secret: {{ include (print $.Template.BasePath "/secret.yaml") . | sha256sum }}
spec:
  automountServiceAccountToken: false
  # k8s injects <SERVICE>_PORT=tcp://<ip>:<port> for services in the namespace,
  # which clashes with the *_PORT env settings the services read
  enableServiceLinks: false
  securityContext:
    {{- toYaml .Values.podSecurityContext | nindent 4 }}
  {{- with .Values.nodeSelector }}
  nodeSelector:
    {{- toYaml . | nindent 4 }}
  {{- end }}
  {{- with .Values.tolerations }}
  tolerations:
    {{- toYaml . | nindent 4 }}
  {{- end }}
  {{- with .Values.topologySpreadConstraints }}
  # constraints without a labelSelector select the pods of this release
  topologySpreadConstraints:
    {{- range . }}
    - {{- toYaml (merge (deepCopy .) (dict "labelSelector" (dict "matchLabels" (include "simcore-service.selectorLabels" $ | fromYaml)))) | nindent 6 }}
    {{- end }}
  {{- end }}
  containers:
    - name: {{ include "simcore-service.name" . }}
      image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
      imagePullPolicy: {{ .Values.image.pullPolicy }}
      {{- with .Values.command }}
      command:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.args }}
      args:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- if .Values.service.enabled }}
      ports:
        - name: http
          containerPort: {{ .Values.containerPort }}
          protocol: TCP
      {{- end }}
      securityContext:
        {{- toYaml .Values.containerSecurityContext | nindent 8 }}
      {{- if .Values.secretEnv }}
      envFrom:
        - secretRef:
            name: {{ include "simcore-service.envSecretName" . }}
      {{- end }}
      {{- with (include "simcore-service.containerEnv" . | trim) }}
      env:
        {{- . | nindent 8 }}
      {{- end }}
      {{- with .Values.probes.startup }}
      startupProbe:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.probes.readiness }}
      readinessProbe:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.probes.liveness }}
      livenessProbe:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      resources:
        {{- toYaml .Values.resources | nindent 8 }}
      volumeMounts:
        - name: tmp
          mountPath: /tmp
        {{- with .Values.extraVolumeMounts }}
        {{- toYaml . | nindent 8 }}
        {{- end }}
  volumes:
    - name: tmp
      emptyDir: {}
    {{- with .Values.extraVolumes }}
    {{- toYaml . | nindent 4 }}
    {{- end }}
{{- end -}}
