# claude-playwright-mcp

Playwright MCP server providing browser automation to Claude Code and claude.ai.
Uses the official `mcr.microsoft.com/playwright/mcp` image with headless Chromium.
Pinned to Hetzner cloud nodes — kept off saraneth to avoid browser load on the
edge node.

## Ingress auth

The ingress uses nginx basic-auth (same pattern as `claude-grocy` and
`claude-waitrose-mcp`). Kubernetes readiness/liveness probes hit the pod
directly and are unaffected.

## Secrets (created out-of-band by Douglas)

**`basic-auth`** — nginx ingress credential (must exist before the deployment
is reachable):

```bash
htpasswd -c -B /tmp/claude/auth douglas
# enter the desired password at the prompt
kubectl -n claude-playwright-mcp create secret generic basic-auth \
  --from-file=auth=/tmp/claude/auth
rm /tmp/claude/auth
```

After creation, add the connector to claude.ai using:
`https://douglas:PASSWORD@playwright.mcp.k3s.fluv.net/mcp`

No `claude-namespace-admin` RoleBinding exists for this namespace — there are
no rotating credentials to manage, so Claude doesn't need secret write access
here. Douglas manages the `basic-auth` secret directly.

## Known limitations

- **No session TTL.** Browser contexts are not cleaned up between MCP calls.
  Leaked contexts accumulate until the pod restarts. Symptom: monotonic memory
  growth up to the 2Gi limit, then OOMKill. Acceptable for initial use;
  KEDA/on-demand session lifecycle is the planned follow-up.
- **Standing Hetzner cost.** `replicas: 1` plus the `instance.hetzner.cloud/provided-by: cloud`
  nodeSelector means the autoscaler cannot scale Hetzner workers to zero while
  this Deployment exists. If Hetzner workers are otherwise transient (spun up
  only for batch workloads), this pod keeps a VM alive permanently. Remove or
  scale to zero when not needed.
- **Single replica.** Browser contexts are in-memory per-process. Multiple
  replicas would produce session routing failures.
- **UID 1000.** Container runs as UID 1000 with `--no-sandbox`. If the image's
  `/app/` or Chromium binaries are not world-readable the pod will fail to start
  with a permissions error — fall back to `runAsNonRoot: false` if needed.

## Endpoints

- `https://playwright.mcp.k3s.fluv.net/mcp` — MCP streamable HTTP endpoint

The egress NetworkPolicy restricts browser requests to ports 80 and 443 only.
Sites served on non-standard ports (e.g. 8080) will be unreachable from this pod.

## Lock-out recovery

If the `basic-auth` Secret is missing or misconfigured, temporarily remove
the auth annotations from the live ingress:

```bash
kubectl -n claude-playwright-mcp annotate ingress playwright-mcp \
  nginx.ingress.kubernetes.io/auth-type- \
  nginx.ingress.kubernetes.io/auth-secret- \
  nginx.ingress.kubernetes.io/auth-realm-
```

Pause Argo CD auto-sync on the Application first.
