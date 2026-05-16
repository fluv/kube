webhook-receiver
================

GitHub webhook receiver in the `claude` namespace. Public ingress at `webhook.k3s.fluv.net/github/deepseek`.

Receives events from the `deepseek-reviewer` GitHub App (installed org-wide on `fluv`) and runs DeepSeek PR reviews, posting results under `fluv-deepseek[bot]`.

v5 (current): pulls a baked image from `ghcr.io/fluv/deepseek-receiver:v<version>` (source at `fluv/.github/deepseek/server/`); ConfigMap-mounted script retired.
v4: migrates to dedicated `deepseek-reviewer` GitHub App; replaces `/ds-recheck` comment trigger with `pull_request.review_requested` event; discovers installation ID at runtime.
v3: adds repo contents snapshot via git tree API (fluv/kube#268).
v2: routes `pull_request` events to DeepSeek PR review pipeline (fluv/claude#816).
v1: HMAC verification and logging only.

Credentials
-----------

The receiver reads from the `deepseek-reviewer-app` k8s secret in the `claude` namespace:

| Key | Value |
|---|---|
| `app-id` | GitHub App ID (or client ID — both work since Oct 2024) |
| `private-key` | PEM private key downloaded from App settings |
| `webhook-secret` | Random string matching the App's webhook secret config |

Installation ID is discovered automatically at first token exchange — no `installation-id` key needed.

Create the secret:

    kubectl -n claude create secret generic deepseek-reviewer-app \
      --from-literal=app-id=<app-id-or-client-id> \
      --from-file=private-key=./deepseek-reviewer.private-key.pem \
      --from-literal=webhook-secret=<webhook-secret>

DeepSeek API key
----------------

DS reviews require a `deepseek` k8s secret with an `api-key` field:

    kubectl -n claude create secret generic deepseek \
      --from-literal=api-key=<your-deepseek-api-key>

The pod starts without it (`optional: true`) but DS reviews are skipped.

Re-requesting a review
----------------------

After pushing fixes in response to DS findings, trigger a re-review by requesting a review from `fluv-deepseek[bot]`:

- **CLI**: `github-app api repos/{repo}/pulls/{N}/requested_reviewers --method POST -f "reviewers[]=fluv-deepseek[bot]"`

This fires a `pull_request.review_requested` event to the receiver.

Updating the script
-------------------

Source lives at `fluv/.github/deepseek/server/`. To cut a new image: bump `version` in `pyproject.toml`, merge to main, then push a matching git tag (e.g. `v1.0.1`). The GHA workflow tags the image as `:v1.0.1` and `:1.0`. Bump the tag in `deployment.yaml` to roll the cluster — ArgoCD will sync the new manifest and trigger a rolling restart:

    kubectl -n claude rollout restart deployment webhook-receiver

Or scale 0→1 if RBAC doesn't cover `rollout restart`.

Smoke test
----------

After the App webhook is configured and secrets are in place, push a commit to any installed repo. Check pod logs:

    kubectl -n claude logs deploy/webhook-receiver --tail=20

Look for `ds_review` → `calling deepseek` → `review posted`. Re-deliveries can be triggered from the App's Recent Deliveries panel at `github.com/settings/apps/deepseek-reviewer`.
