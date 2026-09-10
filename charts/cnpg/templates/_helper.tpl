{{- define "mastodon.podLabels" -}}
{{- with . }}
labels:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- end -}}

{{- define "mastodon.podAnnotations" -}}
{{- with . }}
annotations:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- end -}}

{{- define "mastodon.nodeSelector" -}}
{{- with . }}
nodeSelector:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- end -}}

{{- define "mastodon.affinity" -}}
{{- with . }}
affinity:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- end -}}

{{- define "mastodon.tolerations" -}}
{{- with . }}
tolerations:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- end -}}

{{- define "mastodon.topologySpreadConstraints" -}}
{{- with . }}
topologySpreadConstraints:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- end -}}
