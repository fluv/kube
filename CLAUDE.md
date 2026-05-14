# Claude Code guide for this repo

This is a GitOps repository for a personal two-node k3s cluster managed by Argo CD.

## Cluster layout

| Node | Role | Notes |
|------|------|-------|
| `saraneth` | VPS (Bitfolk), amd64, 4GB RAM | Edge/ingress node; runs non-k8s services (PostgreSQL, Node.js, Tailscale) alongside k3s |
| `pi.home.arpa` | Raspberry Pi 5, arm64, 8GB RAM | Primary workload node |

Nodes are connected via Tailscale. The k3s datastore is PostgreSQL on `saraneth`.

## Grafana dashboards

Dashboard JSON lives in `fluv/grafana`, not here. Grafana syncs from that
repo every 60 seconds — a merge there is live within a minute. Self-merge
permission for dashboard-only changes is granted in that repo's CLAUDE.md.

The ConfigMap dashboard sidecar (`sidecar.dashboards.enabled`) is disabled.
Do not create `grafana_dashboard: "1"` ConfigMaps — they will be silently
ignored. All dashboards go through `fluv/grafana`.

## Making changes

All application configuration goes through Argo CD. Push to `main` and Argo CD
will sync automatically. To apply immediately, trigger a sync in the Argo CD UI.

When adding helm values to an Application manifest, place them under
`spec.source.helm.values`.

Always update the README with a high-level description of the cluster state.
The target audience is passers-by who are unfamilliar with the cluster itself,
but it should contain enough information for a systems administrator to recreate
the configuration on a node from scratch.

## Pre-commit hooks

The repo uses pre-commit hooks (`k8svalidate`, `check-yaml`, whitespace fixes).
These run automatically on commit. To run manually: `pre-commit run --all-files`.

## CRDs

CRDs are managed by the `prometheus-crds` ArgoCD app (`apps/monitoring/prometheus-crds.yaml`). If a missing CRD is causing a sync failure, enable it there — do not `kubectl apply` directly.

Claude's RBAC has cluster-wide read but namespace-scoped write only. Cluster-scoped write operations (CRDs, ClusterRoles, PersistentVolumes) will always return Forbidden — they must go through GitOps.

## Applying node-level changes

Changes to node taints or kubelet config on `saraneth` must be applied manually
via `ssh z` — they are not managed by Argo CD.
