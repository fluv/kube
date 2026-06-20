This repository contains the configuration for my personal Kubernetes cluster.

## Getting this running
To bootstrap anew:
1. provision a cluster (I used [k3s](https://k3s.io/) with `--disable=traefik`)
2. install [Argo CD](https://argo-cd.readthedocs.io/en/stable/getting_started/)
3. sign in and click "new app" then "edit as YAML"
4. paste in the contents of [apps.yaml](apps/apps.yaml)

## Cluster overview

The cluster runs on three node types:

| Node | Role | Notes |
|------|------|-------|
| **Pi** (`pi.home.arpa`) | Control-plane + Pi-local services | Raspberry Pi 5 8GB, arm64, on my desk. Runs Longhorn local disk services, Awair and LG TV exporters (home LAN hardware), and anything explicitly pinned here. |
| **saraneth** | Edge/ingress, non-k8s services | Bitfolk VPS, amd64, 4GB RAM. Tainted `CriticalAddonsOnly=true:PreferNoSchedule` — workloads don&rsquo;t schedule here except ingress-nginx. Hosts ingress-nginx, the k3s datastore (kine/PostgreSQL), and runs Mastodon&rsquo;s Redis and PostgreSQL outside k8s. |
| **Hetzner workers** | Workload nodes | Ephemeral hel1 nodes provisioned by the cluster autoscaler. amd64. All general-purpose Kubernetes workloads land here unless they need LAN access or Pi-specific hardware. |

Nodes are connected via a [**Tailscale**](https://tailscale.com) mesh VPN. The k3s datastore is PostgreSQL (via kine) on `saraneth`. Tailscale routes home-LAN traffic (`192.168.1.0/24`) to all nodes so Pi-scheduled pods can reach home devices.

**Scheduling regime:** saraneth has a `CriticalAddonsOnly=true:PreferNoSchedule` taint — only pods tolerating it (e.g. ingress-nginx) schedule there. Services with home-LAN hardware dependencies (Awair, LG TV) are explicitly pinned to the Pi via nodeSelector. Everything else — stateless services, Loki, Grafana, Prometheus, observability, MCP servers — runs on Hetzner workers. A cluster autoscaler manages worker count; a descheduler runs periodically to consolidate pods onto fewer nodes when demand is low.

## Infrastructure

We&rsquo;re using [**k3s**](https://k3s.io/) for our Kubernetes distribution.

k3s is installed with `--disable=coredns` and `--disable=traefik`. CoreDNS is
fully managed in this repo under `kube/coredns/` and deployed by Argo CD.
Traefik is replaced by Ingress-Nginx.

[**Argo CD**](https://argo-cd.readthedocs.io/en/stable/) drives all cluster
state from this repository. Push to `main` and Argo CD will sync the cluster
within seconds.

For storage, [**Longhorn**](https://longhorn.io/) provides replicated persistent
volumes. The `longhorn-durable` StorageClass targets disks tagged `durable`
by the `longhorn-disk-tagger` DaemonSet — Hetzner worker disks are tagged at
node join; the Pi&rsquo;s SD card and saraneth&rsquo;s disk are excluded.

Two custom PriorityClasses control scheduling under resource pressure:
- `cluster-critical` (value 1,000,000): ingress, Argo CD, cert-manager, Mastodon
- `cluster-low` (value 100, global default): observability, Claude infrastructure, lifestyle services

## Observability

Cluster metrics come from [**Prometheus**](https://prometheus.io/) via the
[`kube-prometheus-stack`](https://github.com/prometheus-community/helm-charts/tree/main/charts/kube-prometheus-stack)
chart. Logs are collected cluster-wide by [**Grafana Alloy**](https://grafana.com/docs/alloy/)
running as a DaemonSet, which tails `/var/log/pods` on each node and ships the
streams to a single-binary [**Grafana Loki**](https://grafana.com/oss/loki/)
instance. Both are surfaced through a [**Grafana**](https://grafana.com/)
instance at `grafana.gentoo-mine.ts.net` with anonymous admin access — no
login, no public ingress; Tailscale ACLs are the access boundary.

A `logging-alerts` PrometheusRule covers the bits that would silently rot:
Loki PVC headroom, stalled ingest, dropped write bytes, and per-node Alloy
coverage.

A second, independent **Lifestyle Prometheus** instance runs in the `lifestyle`
namespace and scrapes personal (non-cluster) metrics:

- **Awair Element air quality** — three Awair Element monitors (bedroom, lounge,
  study) polled via their local HTTP API, exposing CO2, VOC, PM2.5, temperature,
  humidity, and the Awair score. The exporter runs on the Pi to reach devices
  on the home LAN.
- **Grocy** — home inventory and meal-planning metrics from the `claude-grocy`
  namespace.
- **LG TV** — power state, input, volume, and picture-settings metrics from
  the living-room LG WebOS TV via the SSAP WebSocket protocol, pinned to the
  Pi to reach the home LAN.

## Claude bot infrastructure

The `claude` namespace and its sibling `claude-*` namespaces host the
infrastructure Claude (the AI assistant the cluster&rsquo;s owner collaborates with)
relies on: per-app MCP servers (`claude-waitrose-mcp`, `claude-asda-mcp`,
`claude-grocy`, `claude-vestibule`, `claude-notebook`, `claude-printer-mcp`,
`claude-playwright-mcp`), a Prometheus metrics MCP, and
`webhook-receiver`, a small aiohttp service exposed publicly at
`webhook.k3s.fluv.net/github` that receives GitHub App webhooks and
fans them out to in-cluster handlers (DeepSeek PR-review trigger and
event log for claude-monitor).

Claude&rsquo;s MCP servers have no explicit node placement — they run on Hetzner
workers alongside other stateless workloads. The webhook receiver and telemetry
pipeline also run on Hetzner workers.

## End-user services

The `wiki-gsi` namespace runs a private [**MediaWiki**](https://www.mediawiki.org/)
instance at `gsi.gentoo-mine.ts.net` — a personal wiki recovered from a
decade-old installation. MariaDB 11.4 LTS + MediaWiki 1.43 LTS, both pinned to
the Pi.

[**Mastodon**](https://joinmastodon.org/) runs as a single-user instance.
The pods run on Kubernetes (Hetzner workers); PostgreSQL and Redis remain on
`saraneth` outside k8s. User media is stored on Google Cloud Storage.

## Fault tolerance

The cluster tolerates Pi unavailability: saraneth runs ingress-nginx and the
k3s datastore, so the cluster stays reachable if the Pi goes offline. Hetzner
workers are ephemeral by design — any workload that can&rsquo;t tolerate node loss
uses Longhorn replication.

The Pi is the single point for home-LAN hardware services (Awair exporter, LG
TV exporter). These become unavailable if the Pi is offline — accepted, as
they&rsquo;re non-critical. MCP servers run on Hetzner workers and are unaffected by
Pi unavailability.

## Costs

The Raspberry Pi cost £90 (2023), and its 256 GB MicroSD card cost £30 (2025).
Google Cloud storage costs about £1/month.
The Bitfolk VPS base plan costs £65/year plus a RAM upgrade.
Hetzner workers are billed hourly; at theoretical maximum three-node usage,
around €45/month.
Tailscale personal plan is free.
