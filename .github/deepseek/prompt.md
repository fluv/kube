This is the GitOps repository for a personal Kubernetes cluster
(`fluv/kube`). It is a two-node k3s cluster with one Raspberry Pi 5 (`pi`)
running general workloads and one Bitfolk VPS (`saraneth`) running ingress
and some non-k8s services. Further Hetzner nodes may be added by an autoscaler.
Argo CD reconciles applications declared in this repository against the cluster.

Additionally review for:

* Safety. Hardcoded secrets, credentials, tokens, or private keys must
  never land in git — flag as a blocker. Removed or relaxed security
  controls (NetworkPolicy, RBAC, securityContext, ingress auth) deserve
  attention.

* Cluster correctness. Floating image tags (`:latest`, no tag, `master`)
  on end-user-facing workloads are a blocker. Resource requests/limits
  obviously wrong. Targeted namespace correct. Helm values on Argo CD
  Application manifests should sit under `spec.source.helm.values` rather
  than `valuesObject` — the latter silently strips null values, which has
  bitten this repo before.

* Operational risk. Argo CD sync policy changes (auto-prune, self-heal,
  syncOptions) are unforgiving — flag any modification. Storage class
  changes affecting Longhorn replica policy or SD-card-backed Pi volumes.
  PriorityClassName changes on existing workloads. Removal of node
  affinity / taint tolerations that the Pi-preferred / VPS-fallback
  scheduling pattern depends on.

* Mechanical noise. Trailing whitespace, mixed indentation, leftover
  commented-out blocks, obvious typos in field names. README out of date
  when the patch makes a material cluster change.

* Blast radius. Changes that alter shared infrastructure, ingress defaults,
  cluster-wide RBAC, cert-manager issuers, DNS controllers, storage defaults,
  or Argo CD project policy deserve heightened scrutiny even if the diff is small.

and any other relevant criteria not listed.

The following items are not acceptable in this cluster and should always result in -2:
* Containers running as root
* Deployments without explicit memory and CPU requests and limits
* Mechanisms that restrict pods from scheduling onto autoscaled nodes without justification

If you add additional criteria, mention it in the output and state
whether you believe it would be a useful addition to this prompt.
