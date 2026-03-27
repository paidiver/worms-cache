{{- /*
Return the standard Postgres environment variables.
*/ -}}
{{- define "api.postgresEnv" -}}
- name: POSTGRES_HOST
  value: {{ printf "%s-postgresql" .Release.Name }}
- name: POSTGRES_PORT
  value: "{{ .Values.postgresql.primary.service.port }}"
- name: POSTGRES_DB
  value: {{ .Values.postgresql.auth.database }}
- name: POSTGRES_USER
  value: {{ .Values.postgresql.auth.username }}
- name: POSTGRES_PASSWORD
  {{- if .Values.postgresql.auth.existingSecret }}
  valueFrom:
    secretKeyRef:
      name: {{ .Values.postgresql.auth.existingSecret }}
      key: password
  {{- else }}
  value: {{ .Values.postgresql.auth.password }}
  {{ end }}
{{- end -}}
