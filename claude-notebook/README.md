# claude-notebook

Namespace hosting a single service:

- **notebook** — MCP server providing namespaced append-only storage
  (per-namespace JSONL + ULID IDs + tombstone-based deletion + optional
  jq filtering on read). Source in
  [fluv/notebook](https://github.com/fluv/notebook).

Tools exposed: `list_namespaces`, `describe_namespace`, `append`, `get`, `delete`, `search`.

## Storage shape

The single-replica Deployment uses `strategy: Recreate` because the
underlying JSONL is single-writer by design. Data lives on a
ReadWriteOnce Longhorn PVC (`notebook-data`, 1Gi). Do not raise
replicas or switch to RollingUpdate without redesigning the storage
layer — overlapping writers during cutover would corrupt the JSONL.

## Environment variables

| Variable | Default | Effect |
|---|---|---|
| `NOTEBOOK_SENSITIVE_DEFAULT` | *(unset)* | When set to `exclude`, entries whose content contains `"exportable": false` are hidden from bare `get` and `search` calls. Pass `include_sensitive: true` per-call to override. Any other value (including unset) includes all entries. |

## Ingress basic auth

Unlike `claude-asda-mcp` and `claude-waitrose-mcp` (where the upstream
data is public), the notebook holds personal notes — appended content
is sensitive by default. The ingress is gated with basic auth.

The `notebook-auth` Secret (`htpasswd` format) is applied out-of-band;
it is NOT committed to this repo. Provision it manually before the
first deploy:

```
htpasswd -nbB <user> <password> > /tmp/auth
kubectl -n claude-notebook create secret generic notebook-auth --from-file=auth=/tmp/auth
```

## Prerequisites before this app will run

- The `ghcr.io/fluv/notebook` package must be public for the cluster to
  pull it without an `imagePullSecret`. GHCR packages inherit the
  source repo's visibility on first publish; if `fluv/notebook` is
  still private when the first image is pushed, set the package to
  public explicitly (GitHub → Packages → *notebook* → Package settings
  → Change visibility → Public).
- The `notebook-auth` Secret must exist in the namespace (see above).

## Endpoints

- `https://notebook.mcp.k3s.fluv.net/mcp` — MCP streamable HTTP endpoint.
- `https://notebook.mcp.k3s.fluv.net/healthz` — liveness endpoint.
