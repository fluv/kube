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
| **Pi** (`pi.home.arpa`) | Control-plane + Pi-local services | Raspberry Pi 5 8GB, arm64, on my desk. Runs Longhorn local disk services, the Awair and LG TV exporters (home LAN hardware), and anything explicitly pinned here; most Claude MCP servers currently sit here too. |
| **saraneth** | Edge/ingress, non-k8s services | Bitfolk VPS, amd64, 4GB RAM. Cordoned — regular workloads don&rsquo;t schedule here, though DaemonSet pods (which tolerate cordons) still do. Public DNS points here, making it the ingress entry point. Hosts the k3s datastore (kine/PostgreSQL) and runs Mastodon&rsquo;s Redis and PostgreSQL outside k8s. |
| **Hetzner workers** | Workload nodes | Ephemeral hel1 nodes provisioned by the cluster autoscaler. amd64. All general-purpose Kubernetes workloads land here unless they need LAN access or Pi-specific hardware. |

Nodes are connected via a [**Tailscale**](https://tailscale.com) mesh VPN. The k3s datastore is PostgreSQL (via kine) on `saraneth`. Tailscale routes home-LAN traffic (`192.168.1.0/24`) to all nodes so Pi-scheduled pods can reach home devices.

**Scheduling regime:** saraneth is cordoned, so only DaemonSet pods run there. Services with home-LAN or Pi-hardware dependencies (Awair, LG TV) are pinned to the Pi via nodeSelector. Most other workloads — stateless services, Loki, Grafana, Prometheus, observability — run on Hetzner workers. Claude&rsquo;s MCP servers carry no node pinning and land wherever the scheduler puts them (currently mostly the Pi). A cluster autoscaler manages worker count; a descheduler runs periodically to consolidate pods onto fewer nodes when demand is low.

**Ingress:** ingress-nginx runs as a DaemonSet on every node, exposed by k3s ServiceLB on each node&rsquo;s public IP. Public DNS currently points only at saraneth, which proxies to backends across the cluster; round-robin DNS over the worker IPs is planned (#485).

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

The cluster Prometheus retains 8 days of metrics on a 30 GiB Hetzner Cloud
volume (`hcloud-volumes`). A 22 GB `retentionSize` cap sits above the ~16 GB
that 8 days occupies, so it acts only as a backstop against filling the volume —
time-based retention is the binding limit. A `PrometheusRetentionSizeCapBinding`
alert fires if on-disk blocks ever ride near the cap, which would mean data is
being evicted on size before the 8-day window is reached.

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
- **Meaco dehumidifier** — operating state, humidity, and target from the Meaco
  dehumidifier via Tuya protocol, scraped from the in-cluster `meaco-exporter`
  service.
- **Outdoor weather** — temperature, relative humidity, dew point, and absolute
  humidity from the Open-Meteo API (no hardware required), updated every 5 minutes.

## Claude bot infrastructure

The `claude` namespace and its sibling `claude-*` namespaces host the
infrastructure Claude (the AI assistant the cluster&rsquo;s owner collaborates with)
relies on: per-app MCP servers (`claude-waitrose-mcp`, `claude-asda-mcp`,
`claude-grocy`, `claude-vestibule`, `claude-notebook`, `claude-printer-mcp`,
`claude-playwright-mcp`), two Prometheus metrics MCP servers
(`prometheus-mcp` over the cluster Prometheus, `prometheus-mcp-lifestyle`
over the `lifestyle` namespace's Prometheus), and
`webhook-receiver`, a small aiohttp service exposed publicly at
`webhook.k3s.fluv.net/github` that receives GitHub App webhooks and
fans them out to in-cluster handlers (DeepSeek PR-review trigger and
event log for claude-monitor).

Claude&rsquo;s MCP servers have no explicit node placement (playwright-mcp,
pinned to Hetzner, is the exception) — in practice most currently run on the
Pi. The webhook receiver and telemetry pipeline run on Hetzner workers.

## End-user services

The `wiki-gsi` namespace runs a private [**MediaWiki**](https://www.mediawiki.org/)
instance at `gsi.gentoo-mine.ts.net` — a personal wiki recovered from a
decade-old installation. MariaDB 11.4 LTS + MediaWiki 1.43 LTS, both pinned to
the Pi.

[**Mastodon**](https://joinmastodon.org/) runs as a single-user instance.
The pods run on Kubernetes (Hetzner workers); PostgreSQL and Redis remain on
`saraneth` outside k8s. User media is stored on Google Cloud Storage.

A [**Team Fortress 2**](https://www.teamfortress.com/) dedicated server runs in
the `tf2` namespace, deployed by Argo CD from a separate repository,
[`fluv/tf2-server`](https://github.com/fluv/tf2-server). It uses the community
`cm2network/tf2` image, which downloads the ~14&nbsp;GB of game content at runtime
via SteamCMD onto an `emptyDir` &mdash; the server holds no persistent state, so a
rescheduled pod simply re-downloads. The Source engine is x86-only, so the
workload is pinned to amd64 nodes with a `nodeSelector`. It is exposed on UDP
NodePort 30015, and readiness is checked with an [A2S server
query](https://developer.valvesoftware.com/wiki/Server_queries) against the pod
IP rather than a TCP probe, since the game protocol is UDP-only.

## Fault tolerance

The cluster tolerates Pi unavailability: saraneth carries public DNS, an
ingress-nginx pod, and the k3s datastore, so the cluster stays reachable if
the Pi goes offline. Hetzner
workers are ephemeral by design — any workload that can&rsquo;t tolerate node loss
uses Longhorn replication.

The Pi is the single point for home-LAN hardware services (Awair exporter, LG
TV exporter). These become unavailable if the Pi is offline — accepted, as
they&rsquo;re non-critical. Unpinned MCP servers reschedule to Hetzner workers if
the Pi goes away.

## Costs

The Raspberry Pi cost £90 (2023), and its 256 GB MicroSD card cost £30 (2025).
Google Cloud storage costs about £1/month.
The Bitfolk VPS base plan costs £65/year plus a RAM upgrade.
Hetzner workers are billed hourly; at theoretical maximum three-node usage,
around €45/month.
Tailscale personal plan is free.
