# claude-printer-mcp

Namespace hosting a single service:

- **printer-mcp** — MCP server that compiles LaTeX, submits to the Brother
  HL-L2865DW via IPP, and reveals per-page PNGs as each page is announced
  complete. Source in [fluv/printer-mcp](https://github.com/fluv/printer-mcp).
  Design notes in [fluv/claude discussions/890](https://github.com/fluv/claude/discussions/890).

The printer sits on the home LAN at `192.168.1.251`; the Pi reaches it
directly, and the pod is pinned to the Pi via node affinity so all IPP
traffic stays on-LAN (not over Tailscale).

## Ingress basic auth

The endpoint drives a physical printer and must not be open. The ingress
requires basic auth backed by a `basic-auth` secret in the
`claude-printer-mcp` namespace. The secret is created out of band — it
contains credentials and so is deliberately not in git.

To create or rotate the secret:

```bash
htpasswd -nbB <username> <password> | \
  kubectl -n claude-printer-mcp create secret generic basic-auth \
    --from-file=auth=/dev/stdin --dry-run=client -o yaml | \
  kubectl apply -f -
```

## Prerequisites before this app will run

- The `ghcr.io/fluv/printer-mcp` package must be public for the cluster
  to pull it without an `imagePullSecret`.
- The `basic-auth` secret described above must exist; without it the
  ingress returns 503 instead of 401.

## Endpoints

- `https://printer.mcp.k3s.fluv.net/mcp` — MCP streamable HTTP endpoint
- `https://printer.mcp.k3s.fluv.net/healthz` — liveness endpoint

`/metrics` is not exposed externally; the ServiceMonitor scrapes it from
inside the cluster.
