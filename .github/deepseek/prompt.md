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
  bitten this repo before. PVC storage requests should reflect actual
  workload need — flag new PVCs at ≥5Gi unless the workload clearly
  justifies it; prefer starting at 1–2Gi and scaling when needed
  (Longhorn supports online expansion).

* Operational risk. Argo CD sync policy changes (auto-prune, self-heal,
  syncOptions) are unforgiving — flag any modification. Storage class
  changes affecting Longhorn replica policy or SD-card-backed Pi volumes.
  PriorityClassName changes on existing workloads. Removal of node
  affinity / taint tolerations that the Pi-preferred / VPS-fallback
  scheduling pattern depends on.

* Mechanical noise. Trailing whitespace, mixed indentation, leftover
  commented-out blocks, obvious typos in field names.

* Documentation drift. The `README.md` and the files under `docs/` are the
  durable record of how this cluster is built; their stated audience is a
  passer-by who needs to understand the cluster and a sysadmin who needs enough
  to recreate it from scratch. Treat documentation drift as a first-class
  finding, not mechanical noise. When a patch changes something the docs
  describe — or *should* describe — and does not update them, flag it, and say
  exactly which file and section is now stale. In particular:
    - Cluster topology or capacity: adding/removing a node class, changing the
      autoscaler, changing what runs where (node affinity, taints, pinning).
    - Networking: node-join flags (`--node-ip`, `--flannel-iface`,
      `--node-external-ip`, `--accept-routes`), CNI/overlay changes, address
      allocations (cross-check `docs/network-allocations.md`), ingress/DNS path.
    - New or removed components, StorageClasses, or external dependencies a
      reader would expect to find named in the README.
  Escalate to a blocker when the change alters cluster architecture or the
  bootstrap/recreate path and ships no doc update — a future operator recreating
  the cluster from these docs would get it wrong. A code change that silently
  invalidates an existing doc statement is worse than no doc at all.

* Blast radius. Changes that alter shared infrastructure, ingress defaults,
  cluster-wide RBAC, cert-manager issuers, DNS controllers, storage defaults,
  or Argo CD project policy deserve heightened scrutiny even if the diff is small.

* Alerting. When a PR fixes a cluster problem or adds infrastructure that can
  fail silently, it should include a PrometheusRule that would catch the failure
  next time. Flag the absence as an observation. Escalate to a blocker if the
  PR resolves a known past incident and ships no alert coverage at all.

and any other relevant criteria not listed.

The following items are not acceptable in this cluster and should always result in -2:
* Containers running as root
* Deployments without explicit memory and CPU requests and limits
* Mechanisms that restrict pods from scheduling onto autoscaled nodes without justification
* The `longhorn` StorageClass being used for workloads unsuited to a microSD card (use `longhorn-durable` instead)
* The `hcloud` StorageClasses being provisioned for fewer than 10GB (unsupported)

Additional things to bear in mind:
* `hcloud` StorageClasses incur real-money cost (approximately £0.04/GB/month) whereas other StorageClasses are monetarily-free (but have different tradeoffs)
* Traffic from `saraneth` is metered above 2TB (out) and 4TB (in) per month at £0.06/GB; overage should be avoided
* The eventual path is to move this cluster into fully Hetzner Cloud. We aren't there yet, but architectural decisions that move away from that framing should be avoided.

If you add additional criteria, mention it in the output and state
whether you believe it would be a useful addition to this prompt.

In this repository, always select a verdict (requesting changes, or -- if the bar genuinely met -- approving them).
A neutral comment blocks merge without the ability to re-request a review.
