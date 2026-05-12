# claude-waitrose-mcp

Namespace hosting a single service:

- **waitrose-mcp** — MCP server exposing Waitrose product search and
  (once credentials are supplied) authenticated tools. Source in
  [fluv/waitrose-mcp](https://github.com/fluv/waitrose-mcp).

Tools exposed: `search_products`, `browse_products`,
`get_products_by_line_numbers`, `get_promotion_products`. Authenticated
tools (trolley, orders, slots) activate automatically when the server logs
in via `WAITROSE_USERNAME` / `WAITROSE_PASSWORD` at startup.

## Ingress auth

The ingress uses nginx basic-auth (matching `claude-grocy` and
`claude-vestibule`). All paths — including `/healthz` — require credentials.
Kubernetes readiness/liveness probes are unaffected because they hit the pod
directly via the service IP, not through the ingress.

## Secrets (created out-of-band by Douglas)

Two Secrets in the `claude-waitrose-mcp` namespace. Neither is committed to
this repo.

**`basic-auth`** — nginx ingress credential:

```bash
htpasswd -c -B /tmp/claude/auth claude
# enter the desired password at the prompt
kubectl -n claude-waitrose-mcp create secret generic basic-auth \
  --from-file=auth=/tmp/claude/auth
rm /tmp/claude/auth
```

After creation, update the saved credentials in the claude.ai MCP
integrations console for the Waitrose connector.

**`waitrose-credentials`** — Waitrose account for authenticated tools:

```bash
kubectl -n claude-waitrose-mcp create secret generic waitrose-credentials \
  --from-literal=WAITROSE_USERNAME='<email>' \
  --from-literal=WAITROSE_PASSWORD='<password>'
```

The pod picks these up via `envFrom` and logs in at startup. Pod logs will
show `[INIT] Authenticated as <email>` on success.

## Lock-out recovery

If the `basic-auth` Secret is missing or misconfigured and you can't reach
the MCP, temporarily remove the auth annotations from the live ingress:

```bash
kubectl -n claude-waitrose-mcp annotate ingress waitrose-mcp \
  nginx.ingress.kubernetes.io/auth-type- \
  nginx.ingress.kubernetes.io/auth-secret- \
  nginx.ingress.kubernetes.io/auth-realm-
```

Pause Argo CD auto-sync on the Application first — otherwise it re-applies
the annotations within a minute.

## Prerequisites before this app will run

The `ghcr.io/fluv/waitrose-mcp` package must be public for the cluster to
pull it without an `imagePullSecret`. GHCR packages inherit the source
repository's visibility on first publish; if the `fluv/waitrose-mcp`
repo is still private when the first image is pushed, the package needs
to be set to public explicitly (GitHub → Packages → *waitrose-mcp* →
Package settings → Change visibility → Public). Same pattern as
`claude-grocy`, `claude-vestibule`, `router-mcp`.

## Endpoints

- `https://waitrose.mcp.k3s.fluv.net/mcp` — MCP streamable HTTP endpoint
- `https://waitrose.mcp.k3s.fluv.net/healthz` — liveness endpoint

## Why `claude-waitrose-mcp` (namespace)

The `claude` Argo CD project permits destinations in namespaces matching
`claude` or `claude-*`. Naming the namespace `claude-waitrose-mcp` keeps
the app under that project without widening its destination allowlist.
