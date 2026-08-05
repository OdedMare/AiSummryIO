{{- define "aisummry-backend.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "aisummry-backend.fullname" -}}
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

{{- define "aisummry-backend.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "aisummry-backend.labels" -}}
helm.sh/chart: {{ include "aisummry-backend.chart" . }}
{{ include "aisummry-backend.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "aisummry-backend.selectorLabels" -}}
app.kubernetes.io/name: {{ include "aisummry-backend.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "aisummry-backend.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "aisummry-backend.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Name of the Secret this chart creates for values supplied inline. Values
pointing at an existing Secret bypass it.
*/}}
{{- define "aisummry-backend.secretName" -}}
{{- printf "%s-secrets" (include "aisummry-backend.fullname" .) }}
{{- end }}

{{/*
True when at least one inline secret value was supplied, meaning the chart
must render its own Secret.
*/}}
{{- define "aisummry-backend.createSecret" -}}
{{- if or (and .Values.database.url (not .Values.database.existingSecret))
          (and .Values.llm.apiKey (not .Values.llm.existingSecret))
          (and .Values.flapi.token (not .Values.flapi.existingSecret))
          (and .Values.auth.adminPassword (not .Values.auth.existingSecret))
          (and .Values.auth.cookieSecret (not .Values.auth.existingSecret)) -}}
true
{{- end -}}
{{- end }}
