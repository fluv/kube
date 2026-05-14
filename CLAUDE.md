# Claude Code guide for this repo

This is a GitOps repository for a personal two-node k3s cluster managed by Argo CD.

## Cluster layout

| Node | Role | Notes |
|------|------|-------|
| `saraneth` | VPS (Bitfolk), amd64, 4GB RAM | Edge/ingress node; runs non-k8s services (PostgreSQL, Node.js, Tailscale) alongside k3s |
| `pi.home.arpa` | Raspberry Pi 5, arm64, 8GB RAM | Primary workload node |

Nodes are connected via Tailscale. The k3s datastore is PostgreSQL on `saraneth`.
Additional ephemeral nodes in Hetzner Cloud are provisioned when required by an autoscaler.
Tailscale is configured so that any node can hit the 192.168.1.0/24 domestic home network.

## Grafana dashboards

Dashboard JSON lives in `fluv/grafana`, not here. Grafana syncs from that
repo every 60 seconds — a merge there is live within a minute. Self-merge
permission for dashboard-only changes is granted in that repo's CLAUDE.md.

The ConfigMap dashboard sidecar (`sidecar.dashboards.enabled`) is disabled.
Do not create `grafana_dashboard: "1"` ConfigMaps — they will be silently
ignored. All dashboards go through `fluv/grafana`.

## Making changes

All cluster state goes through Argo CD. If something needs to exist in the cluster, it belongs in this repo. `kubectl apply` is not a workaround; if ArgoCD can't sync a resource, fix the ArgoCD config.

Exception: secrets are not stored in git. Claude has secret write access in its own namespaces only (see `claude/rbac.yaml`).

Push to `main` and Argo CD will sync automatically.

When adding helm values to an Application manifest, place them under
`spec.source.helm.values`.

Always update the README with a high-level description of the cluster state.
The target audience is passers-by who are unfamilliar with the cluster itself,
but it should contain enough information for a systems administrator to recreate
the configuration on a node from scratch.

## Pre-commit hooks

The repo uses pre-commit hooks (`k8svalidate`, `check-yaml`, whitespace fixes).
These run automatically on commit. To run manually: `pre-commit run --all-files`.

## Claude's RBAC

Cluster-wide read, namespace-scoped write. Cluster-scoped writes (CRDs, ClusterRoles, PersistentVolumes) will always return Forbidden — not a permissions gap to work around, by design.

## Alerting

"Is the cluster healthy?" is answered by "are any alerts firing?" — not by checking dashboards.

When fixing a cluster problem — a pod crashlooping, a service degraded, a disk filling, a node under load — include a PrometheusRule in the same PR that would have caught it. The fix and the alert belong together; the alert is what makes the fix durable.

PrometheusRules live in `logging-alerts/` or alongside their workload manifest. Use `severity: warning` for degraded-but-not-broken, `severity: critical` for imminent failure or data loss.

## Applying node-level changes

Changes to node taints or kubelet config on `saraneth` must be applied manually
via `ssh z` — they are not managed by Argo CD.
