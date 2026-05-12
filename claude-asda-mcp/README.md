# claude-asda-mcp

Namespace hosting a single service:

- **asda-mcp** — MCP server exposing Asda product search via Algolia.
  Source in [fluv/asda-mcp](https://github.com/fluv/asda-mcp).

Tools exposed: `search_products`, `get_products_by_cin`, `browse_products`.
All anonymous — Asda's Algolia search key is a public-facing client key
embedded in their frontend JS.

## No ingress basic auth

Like `claude-waitrose-mcp`, this ingress is unauthenticated — the upstream
data is public and there is no write surface to gate.

## Prerequisites before this app will run

The `ghcr.io/fluv/asda-mcp` package must be public for the cluster to pull
it without an `imagePullSecret`. GHCR packages inherit the source repo's
visibility on first publish; if `fluv/asda-mcp` is still private when the
first image is pushed, set the package to public explicitly (GitHub →
Packages → *asda-mcp* → Package settings → Change visibility → Public).

## Endpoints

- `https://asda.mcp.k3s.fluv.net/mcp` — MCP streamable HTTP endpoint
- `https://asda.mcp.k3s.fluv.net/healthz` — liveness endpoint
