<!-- ai-generated: 100% - Claude Code (Opus 5.5) wrote this file; the lecturer reviews it -->
# Kubernetes track (L3-STRETCH-3)

The reference ships the three manifests but no `evidence.json`: it was not run on a kind cluster, so this option
fails here by design and the reference earns its Stretch with the other two. A student on the track installs
kube-prometheus-stack 89.2.2 with `values.yaml`, applies the two manifests, and saves
`kubectl get prometheusrules,servicemonitors,pods -A -o json > k8s/evidence.json`.
