This repository contains the configuration for my personal Kubernetes cluster.

## Getting this running
To bootstrap anew:
1. provision a cluster (I used [k3s](https://k3s.io/) with `--disable=traefik`)
2. install [Argo CD](https://argo-cd.readthedocs.io/en/stable/getting_started/)
3. sign in and click "new app" then "edit as YAML"
4. paste in the contents of [apps.yaml](apps/apps.yaml)

## Cluster overview

I have two stable Kubernetes nodes at the moment.
One of them is on my [**Bitfolk**](https://bitfolk.com) VPS, which is your standard
Debian server running in a datacentre somewhere. Its hostname is `saraneth`.

The other is a [**Raspberry Pi 5** 8GB](https://www.raspberrypi.com/products/raspberry-pi-5/)
running on my desk. Its hostname is `pi`.

They&rsquo;re connected together via a [**Tailscale**](https://tailscale.com) mesh
virtual private network using the k3s [experimental integration](https://docs.k3s.io/networking/distributed-multicloud#integration-with-the-tailscale-vpn-provider-experimental).

As my VPS already had a PostgreSQL server running, we&rsquo;re using that for
the cluster datastore. The `saraneth` node has a
`CriticalAddonsOnly=true:PreferNoSchedule` taint to try and push as much work
onto the Raspberry Pi as possible; the VPS&rsquo;s job is to run the control plane
and serve the ingress traffic to the outside world.
Ingress-nginx is pinned to `saraneth` via a nodeSelector.

As the VPS runs non-Kubernetes services alongside k3s, kubelet resource
reservations are configured manually on `saraneth` to prevent Kubernetes from
consuming the whole host. This means there isn't actually much compute available
for Kubernetes workloads, so we also use a **cluster autoscaler** which spins up
new nodes as required in **Hetzner Cloud**. A descheduler is configured to run
occasionally and evict pods from underutilised nodes, cramming them into as few
nodes as possible, to keep costs down.

## Projects

### Infrastructure

We&rsquo;re using [**k3s**](https://k3s.io/) for our Kubernetes distribution.
I picked it as it was lightweight enough to run on my VPS alongside all the
other non-Kubernetes things my VPS is doing, while being portable enough that
I could feasibly run it on any hardware I might want to extend this cluster to
in the future. It also came bundled with some integrations out the box that made
my life easier.

k3s is installed with `--disable=coredns` and `--disable=traefik`. CoreDNS is
fully managed in this repo under `kube/coredns/` (ConfigMap, ServiceAccount,
RBAC, DaemonSet, and Service) and deployed by Argo CD — not by the k3s addon
system. Traefik is replaced by Ingress-Nginx (see below).

We&rsquo;re running [**Argo CD**](https://argo-cd.readthedocs.io/en/stable/),
which is used to facilitate &ldquo;declarative GitOps&rdquo;: when you push
some YAML code to this repository, Argo CD will notice the change and will take
action to make sure the state of the Kubernetes cluster aligns with the code
you wrote.

We are using [**Ingress-Nginx**](https://kubernetes.github.io/ingress-nginx/) and
[**cert-manager**](https://cert-manager.io/) to expose our HTTP/HTTPS services to
the outside world. As we&rsquo;re using this instead of Traefik, the ingress
controller that is bundled with k3s, we can install k3s with the
`--disable=traefik` flag to save some overhead. I chose to use Ingress-Nginx as
I was already familiar with it.

For volumes and storage, we&rsquo;re using [**Longhorn**](https://longhorn.io/),
which means that any persistent storage used by our containers will, by default,
be replicated in both nodes. As I want to run some applications that have heavy
read/write activity, I have configured a StorageClass that removes SD cards from
the pool where needed.

### Observability

Cluster metrics come from [**Prometheus**](https://prometheus.io/) via the
[`kube-prometheus-stack`](https://github.com/prometheus-community/helm-charts/tree/main/charts/kube-prometheus-stack)
chart. Logs are collected cluster-wide by [**Grafana Alloy**](https://grafana.com/docs/alloy/)
running as a DaemonSet, which tails `/var/log/pods` on each node and ships the
streams to a single-binary [**Grafana Loki**](https://grafana.com/oss/loki/)
instance pinned to the Pi. Both are surfaced through a
[**Grafana**](https://grafana.com/) instance exposed on the tailnet at
`grafana.gentoo-mine.ts.net` with anonymous admin access — no login, no public
ingress; Tailscale ACLs are the access boundary.

The cluster Prometheus retains 8 days of metrics on a 30 GiB Hetzner Cloud
volume (`hcloud-volumes`). A 22 GB `retentionSize` cap sits above the ~16 GB
that 8 days occupies, so it acts only as a backstop against filling the volume —
time-based retention is the binding limit. A `PrometheusRetentionSizeCapBinding`
alert fires if on-disk blocks ever ride near the cap, which would mean data is
being evicted on size before the 8-day window is reached.

A `logging-alerts` PrometheusRule covers the bits that would silently rot:
Loki PVC headroom, stalled ingest, dropped write bytes, and per-node Alloy
coverage. All logging components run at `cluster-low` priority so they yield
to end-user workloads under memory pressure on `saraneth`.

A second, independent **Lifestyle Prometheus** instance runs in the `lifestyle`
namespace and scrapes personal (non-cluster) metrics. Current scrapers:

- **Awair Element air quality** — three Awair Element monitors (bedroom, lounge,
  study) polled via their local HTTP API, exposing CO₂, VOC, PM2.5, temperature,
  humidity, and the Awair score. The exporter runs with `hostNetwork: true` on
  the Pi to reach devices on the home LAN.
- **Grocy** — home inventory and meal-planning metrics from the `claude-grocy`
  namespace.
- **LG TV** — power state, input, volume, and picture-settings metrics from
  the living-room LG WebOS TV via the SSAP WebSocket protocol (bscpylgtv),
  pinned to the Pi to reach the home LAN.
- **Meaco dehumidifier** — operating state, humidity, and target from the Meaco
  dehumidifier via Tuya protocol, scraped from the in-cluster `meaco-exporter`
  service.
- **Outdoor weather** — temperature, relative humidity, dew point, and absolute
  humidity from the Open-Meteo API (no hardware required), updated every 5 minutes.

## Claude bot infrastructure

The `claude` namespace and its sibling `claude-*` namespaces host the
infrastructure Claude (the AI assistant the cluster's owner collaborates with)
relies on: per-app MCP servers (`claude-waitrose-mcp`, `claude-asda-mcp`,
`claude-grocy`, `claude-vestibule`, `claude-notebook`, `claude-printer-mcp`,
`claude-playwright-mcp`), two Prometheus metrics MCP servers
(`prometheus-mcp` over the cluster Prometheus, `prometheus-mcp-lifestyle`
over the `lifestyle` namespace's Prometheus), and
`webhook-receiver`, a small aiohttp service exposed publicly at
`webhook.k3s.fluv.net/github` that receives GitHub App webhooks and
fans them out to in-cluster handlers (initially: a DeepSeek PR-review
trigger and a replacement for the polling-based `claude-monitor`).

## End-user services

The `slipway` namespace runs [**slipway**](https://github.com/fluv/slipway), a
small Go service that renders recorded household data (Grocy stock, lifestyle
Prometheus series) and nearby public map to-do lists (open OpenStreetMap notes,
Wikidata items lacking an image) as a short daily list of concrete prompts,
gated by the Open-Meteo precipitation forecast. Tailnet-only at
`slipway.gentoo-mine.ts.net`; scraped by the lifestyle Prometheus.

The `wiki-gsi` namespace runs a private [**MediaWiki**](https://www.mediawiki.org/)
instance at `gsi.gentoo-mine.ts.net` — a personal wiki recovered from a decade-old
installation. It consists of a MariaDB 11.4 LTS database (seeded from the original
raw data directory) and a MediaWiki 1.43 LTS pod, both pinned to the Pi. The wiki is
private; only authenticated users with the `user` group or above can read or edit.

We&rsquo;re running a single-user [**Mastodon**](https://joinmastodon.org/) instance on
Kubernetes. This used to run solely on my VPS, but this caused problems: it is
a disconcertingly resource-intensive Ruby program, and it meant my VPS often
ran out of RAM and fell offline halfway through an upgrade.

I&rsquo;m using a hybrid solution at the moment. The pods are running in Kubernetes,
but I&rsquo;m still using the old PostgreSQL and Redis servers that were already on
my VPS for the "important" stuff. Instead of using Kubernetes persistent volumes,
we&rsquo;re using [Google Cloud Storage](https://cloud.google.com/storage) for
user data.

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

The server spends most of its life empty, so it scales to zero when idle. A
tiny always-on &ldquo;knocker&rdquo; pod (`tf2-knocker/`, a Python script from a
ConfigMap on a stock `python:slim` image) shares the `app: tf2` Service
selector and reports ready only while the real server has no ready replicas,
so the Service&rsquo;s endpoints flip between the two automatically. While the
server sleeps, the knocker answers A2S queries itself with a fake
&ldquo;sleeping&rdquo; response &mdash; keeping the server browser and `tf2-web`
status page working without waking anything &mdash; and scales the deployment
to 1 on the first real connect packet; once the server is up, it scales back
to 0 after 30 minutes with no players. The `tf2-server` Application ignores
replica-count drift so Argo CD doesn&rsquo;t fight the knocker. A cold wake
re-downloads the game content, so joining a sleeping server takes minutes,
not seconds.

## Fault tolerance

I can reasonably expect my VPS to be up and running at all times.
It&rsquo;s in a datacentre backed by proper hardware.
It is comparatively resource-bound, though: we&rsquo;re low on disk space and have
contention for CPU with other Bitfolk tenants.

My Raspberry Pi cannot be trusted to be as reliable.
I want to be able to unplug the Raspberry Pi to move things around in my office
with no notice, or the MicroSD card upon which it runs to fail at any moment.
However, the storage is cheap and all the hardware is available for my sole use.

As such:
* having the cluster data store only on the VPS is fine
* any persistent storage on the Pi must also be stored on the VPS
* the node on the VPS has a `CriticalAddonsOnly=true:PreferNoSchedule` taint to
  encourage pods to be scheduled elsewhere if possible, while still allowing it
  to step in if needed (which `…:NoSchedule` would prevent)
* workloads with pi-specific dependencies (LAN access, local file reads) use
  a `preferredDuringSchedulingIgnoredDuringExecution` node affinity for the
  Pi or a hard `nodeSelector`; other workloads are unconstrained — saraneth's
  kubelet reservations and the `cluster-low` priority class protect it
  from over-scheduling
* two custom PriorityClasses control which workloads actually get resources on
  the VPS during a Pi outage: `cluster-critical` (value 1000000) for services
  like Mastodon, Argo CD, cert-manager and ingress-nginx, and
  `cluster-low` (value 100, global default) for everything else. When the VPS
  runs low on memory, low-priority pods are preempted to make room for critical
  ones


## Costs

The Raspberry Pi cost me £90 (2023), and its 256GB MicroSD card cost £30 (2025).
Google Cloud storage, used for Mastodon,  costs me about £1 a month.
A base plan on my VPS costs £65 a year, and I pay extra for some additional RAM.

Hetzner nodes are billed hourly. At theoretical maximum usage that's around €45/month.

I&rsquo;m using the personal Tailscale plan, which is free.
