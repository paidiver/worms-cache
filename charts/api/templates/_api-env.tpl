
{{/*
PostgreSQL connection credentials used by all api-*.yaml files
*/}}
{{- define "worms-cache-api.dbEnv" -}}
- name: POSTGRES_HOST
  value: {{ .Values.db.host | quote }}
- name: POSTGRES_PORT
  value: {{ .Values.db.port | default "5432" | quote }}
- name: POSTGRES_DB
  value: "{{ .Values.auth.database }}"
- name: POSTGRES_USER
  value: "{{ .Values.auth.username }}"
- name: POSTGRES_PASSWORD
  {{- if .Values.auth.existingSecret }}
  valueFrom:
    secretKeyRef:
      name: {{ .Values.auth.existingSecret }}
      key: password
  {{- else }}
  value: {{ .Values.auth.password }}
  {{ end }}
- name: DB_HOST
  value: {{ .Values.db.host | quote }}
- name: DB_PORT
  value: {{ .Values.db.port | default "5432" | quote }}
- name: DB_NAME
  value: "{{ .Values.auth.database }}"
- name: DB_USER
  value: "{{ .Values.auth.username }}"
- name: DB_PASSWORD
  {{- if .Values.auth.existingSecret }}
  valueFrom:
    secretKeyRef:
      name: {{ .Values.auth.existingSecret }}
      key: password
  {{- else }}
  value: {{ .Values.auth.password }}
  {{ end }}
{{- end -}}
