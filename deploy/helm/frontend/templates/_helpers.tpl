{{- define "aisummry-frontend.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "aisummry-frontend.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{- define "aisummry-frontend.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "aisummry-frontend.labels" -}}
helm.sh/chart: {{ include "aisummry-frontend.chart" . }}
{{ include "aisummry-frontend.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "aisummry-frontend.selectorLabels" -}}
app.kubernetes.io/name: {{ include "aisummry-frontend.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "aisummry-frontend.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "aisummry-frontend.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
The URL next.config.ts proxies /api/* to. An explicit `backend.url` wins;
otherwise reconstruct the backend chart's Service DNS name, which is
"<release>-aisummry-backend" under that chart's default naming.
*/}}
{{- define "aisummry-frontend.backendUrl" -}}
{{- if .Values.backend.url -}}
{{- .Values.backend.url -}}
{{- else -}}
{{- $release := default .Release.Name .Values.backend.releaseName -}}
{{- printf "http://%s-aisummry-backend:%v" $release .Values.backend.port -}}
{{- end -}}
{{- end }}
