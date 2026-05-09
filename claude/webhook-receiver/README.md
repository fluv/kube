webhook-receiver
================

GitHub webhook receiver. Verifies HMAC-SHA256, logs the event. Single Pi-affinity replica in the `claude` namespace, public ingress at `webhook.k3s.fluv.net/github`.

Status: v1, smoke-test only. See zuzak/claude#200 (event log for `claude-monitor`) and zuzak/claude#816 (DS review handler) for the consumers that build on this.

Why a stock python image
------------------------

The deployment uses `python:3.13-slim` and pip-installs `aiohttp` at startup, rather than a baked image. Reason: GitHub Actions billing was exhausted when this was first deployed, so the usual `ghcr.io/zuzak/...` image build wasn't an option. Promote to a proper image once Actions is back and once a second consumer (DS handler, monitor consumer) makes the dependency surface non-trivial.

Updating the script
-------------------

The Python source is inlined into `configmap.yaml`. After editing, push to main and trigger an Argo sync. The pod does **not** automatically restart on ConfigMap changes — kick it manually:

    kubectl -n claude rollout restart deployment webhook-receiver

Or scale 0→1 if your RBAC doesn't include `rollout restart`.

Webhook secret
--------------

The receiver reads `WEBHOOK_SECRET` from the `claude-github-app` k8s secret (key `webhook-secret`). Generate with `openssl rand -hex 32` and patch into the secret:

    kubectl -n claude patch secret claude-github-app --type=json \
      -p='[{"op":"add","path":"/data/webhook-secret","value":"'"$(openssl rand -hex 32 | base64 -w0)"'"}]'

Configure the same value as the webhook secret on the GitHub App settings page.

Smoke test
----------

After the App webhook is configured, push a commit to any installed repo. Pod logs should show a single line per event:

    kubectl -n claude logs deploy/webhook-receiver --tail=20

A `received_at` field plus the GitHub `delivery` ID indicates the receiver got the event. Re-deliveries can be triggered from the App's Recent Deliveries panel for repeatable testing.
