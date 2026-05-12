webhook-receiver
================

GitHub webhook receiver in the `claude` namespace. Public ingress at `webhook.k3s.fluv.net/github`.

v3 (current): adds repo contents snapshot via git tree API (fluv/kube#268). DS now sees the full repo at HEAD (capped at 400KB, with per-repo `exclude_prefixes` honoured) alongside patch + prior thread. Per-repo `exclude_prefixes` lives in `REPO_CONFIG` inside `script.py`; e.g. `fluv/claude` skips `projects/` and `dot-claude/projects/`, `fluv/kube` skips nothing.

v2: routes `pull_request` and `issue_comment` events to a DeepSeek PR review pipeline (fluv/claude#816). Reviews posted under `claude-zuzak[bot]` using the existing GitHub App credentials.

Why a stock python image
------------------------

The deployment uses `python:3.13-slim` and pip-installs `aiohttp PyJWT cryptography` at startup, rather than a baked image. Reason: GitHub Actions billing was exhausted when this was first deployed. Promote to a proper image once Actions is back.

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

DeepSeek API key
----------------

DS reviews require a `deepseek` k8s secret with an `api-key` field. Create it with:

    kubectl -n claude create secret generic deepseek \
      --from-literal=api-key=<your-deepseek-api-key>

The pod starts without it (env var is `optional: true`) but DS reviews are skipped — the startup log will say "DS review disabled".

Self-review behaviour
---------------------

GitHub rejects `APPROVE` and `REQUEST_CHANGES` reviews when the reviewer is the PR author. When `claude-zuzak[bot]` opens a PR, the DS pipeline falls back to posting the review body as a plain issue comment rather than a formal review. The verdict markers (`<!-- APPROVE -->` etc.) are preserved in the comment text so author-side parsing still works. No Reviews-tab verdict appears for bot-authored PRs — this is expected and not a bug.

Smoke test
----------

After the App webhook is configured and the DeepSeek secret is in place, push a commit to any installed repo. Pod logs:

    kubectl -n claude logs deploy/webhook-receiver --tail=20

Look for `ds_review` then `calling deepseek` then `review posted`. Re-deliveries can be triggered from the App's Recent Deliveries panel.
