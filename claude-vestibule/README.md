# claude-vestibule

Namespace hosting two coupled services:

- **vestibule** — internal HTTP proxy that holds upstream credentials and
  enforces politeness toward upstream APIs. ClusterIP only; no ingress.
  See [fluv/vestibule](https://github.com/fluv/vestibule).
- **vestibule-mcp** — public-facing MCP server. Reads vestibule's
  `/_manifest` at startup and exposes declared endpoints as MCP tools.
  See [fluv/vestibule/mcp](https://github.com/fluv/vestibule/tree/main/mcp).

The MCP is the product; vestibule is its dependency. Claude Chat (and
any other MCP client on the allowlist) connects to the MCP ingress, not
to vestibule directly.

## Sync ordering

Argo CD sync waves keep vestibule starting before vestibule-mcp — the
MCP fetches the manifest once at startup and will fail to start if
vestibule isn't reachable.

| Resource | Wave |
|---|---|
| `vestibule` Deployment | 0 |
| `vestibule-mcp` Deployment | 1 |

## Prerequisites before this app will run

Three things must happen out-of-band, because they cannot live in this
public repo.

### 1. Apply the `vestibule-config` Secret

The proxy reads its YAML config from the file path `VESTIBULE_CONFIG`
(set to `/etc/vestibule/config.yaml` in the Deployment). The config is
mounted from the `vestibule-config` Secret, key `config.yaml`.

Prepare the config locally using the schema in the vestibule repo's
`example.yaml` — including the `mcp.tool_name` block on each endpoint
you want exposed as a tool — then apply:

```
kubectl create secret generic vestibule-config \
  --namespace claude-vestibule \
  --from-file=config.yaml=./config.yaml
```

Roll both Deployments to pick up the new contents:

```
kubectl rollout restart deployment/vestibule -n claude-vestibule
kubectl rollout restart deployment/vestibule-mcp -n claude-vestibule
```

(The MCP is restarted too because it re-reads the manifest at startup.)

Do not commit the real config to any repo — public or private. The
credentials live in the cluster's secret store and nowhere else.

### 2. Apply the `vestibule-mcp-auth` Secret (ingress basic auth)

The MCP ingress is gated by ingress-nginx basic auth, matching the
pattern used by `claude-grocy`. The Secret is a standard htpasswd and
is **not** committed to this repo. Create it out-of-band:

```
htpasswd -c ./vestibule-mcp.htpasswd <username>
kubectl create secret generic vestibule-mcp-auth \
  --namespace claude-vestibule \
  --from-file=auth=./vestibule-mcp.htpasswd
rm ./vestibule-mcp.htpasswd
```

### 3. Make the GHCR packages public (first deploy only)

Both `ghcr.io/fluv/vestibule` and `ghcr.io/fluv/vestibule-mcp` need to
be public for the cluster to pull without an `imagePullSecret`. GHCR
packages inherit the source repository's visibility on first publish;
until the vestibule repo is made public, each package needs to be set
to public explicitly (GitHub → Packages → *package name* → Package
settings → Change visibility → Public), or an `imagePullSecret` added
to both Deployments. Other Claude-facing apps in this cluster
(`claude-grocy`, `router-mcp`) rely on public packages, so this
follows the existing pattern.

## Endpoints

- `https://vestibule-mcp.mcp.k3s.fluv.net/mcp` — MCP streamable HTTP
  endpoint (behind ingress basic auth). This is what Claude Chat
  connects to.
- `https://vestibule-mcp.mcp.k3s.fluv.net/healthz` — MCP liveness
  endpoint, reachable through the ingress.
- `vestibule.claude-vestibule.svc.cluster.local:8080/healthz` —
  vestibule's in-cluster liveness/readiness endpoint.
- `vestibule.claude-vestibule.svc.cluster.local:8080/_manifest` —
  vestibule's manifest; consumed once by the MCP at startup.
- `vestibule.claude-vestibule.svc.cluster.local:9090/metrics` and
  `vestibule-mcp.claude-vestibule.svc.cluster.local:9090/metrics` —
  Prometheus scrape targets, pod-network only; **never** exposed via
  ingress.

## Why `claude-vestibule` (namespace) and not `vestibule`

The `claude` Argo CD project permits destinations in namespaces
matching `claude` or `claude-*`. Naming the namespace
`claude-vestibule` keeps the app under that project without widening
its destination allowlist. The MCP lives in the same namespace because
the two services are coupled and share a lifecycle.
