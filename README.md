This repository contains the configuration for my personal Kubernetes cluster.

## Getting this running
To bootstrap anew:
1. provision a cluster (I used [k3s](https://k3s.io/) with `--disable=traefik`)
2. install [Argo CD](https://argo-cd.readthedocs.io/en/stable/getting_started/)
3. sign in and click "new app" then "edit as YAML"
4. paste in the contents of [apps.yaml](apps/apps.yaml)

## Cluster overview

I have two permanent Kubernetes nodes.
One of them is on my [**Bitfolk**](https://bitfolk.com) VPS, which is your standard
Debian server running in a datacentre somewhere. Its hostname is `saraneth`.

The other is a [**Raspberry Pi 5** 8GB](https://www.raspberrypi.com/products/raspberry-pi-5/)
running on my desk. Its hostname is `pi`.

They&rsquo;re connected together via a [**Tailscale**](https://tailscale.com) mesh
virtual private network using the k3s [experimental integration](https://docs.k3s.io/networking/distributed-multicloud#integration-with-the-tailscale-vpn-provider-experimental).

When the two permanent nodes don&rsquo;t have enough room, an autoscaler adds
extra nodes in [**Hetzner Cloud**](https://www.hetzner.com/cloud) and removes
them again once they&rsquo;re no longer needed. The Hetzner nodes are on their
own normal private network for speed, but we use Tailscale when they need to
talk to the other nodes.

As my VPS already had a PostgreSQL server running, we&rsquo;re using that for
the cluster datastore. The `saraneth` node has a
`CriticalAddonsOnly=true:PreferNoSchedule` taint to try and push as much work
onto the Raspberry Pi as possible; the VPS&rsquo;s job is to run the control plane
and serve the ingress traffic to the outside world.
Ingress-nginx is pinned to `saraneth` via a nodeSelector.

As the VPS runs non-Kubernetes services alongside k3s, kubelet resource
reservations are configured manually on `saraneth` to prevent Kubernetes from
consuming the whole host. These should be placed in
`/etc/rancher/k3s/config.yaml.d/kubelet-reservations.yaml`:

```yaml
kubelet-arg:
  - "system-reserved=cpu=500m,memory=1250Mi"
  - "kube-reserved=cpu=300m,memory=700Mi"
  - "eviction-hard=memory.available<300Mi,nodefs.available<10%"
```

## Projects

### Infrastructure

We&rsquo;re using [**k3s**](https://k3s.io/) for our Kubernetes distribution.
I picked it as it was lightweight enough to run on my VPS alongside all the
other non-Kubernetes things my VPS is doing, while being portable enough that
I could feasibly run it on any hardware I might want to extend this cluster to
in the future. It also came bundled with some integrations out the box that made
my life easier.

I&rsquo;ve also told k3s not to install its own copy of CoreDNS
(`--disable=coredns`) and run my own through Argo CD instead, so I can configure
it however I need to.

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

For keeping an eye on things I use [**Prometheus**](https://prometheus.io/) to
collect metrics and [**Grafana Loki**](https://grafana.com/oss/loki/) for logs,
with [**Grafana Alloy**](https://grafana.com/docs/alloy/) running on every node
to gather the logs up and ship them to Loki on the Pi. I look at all of it
through [**Grafana**](https://grafana.com/), which sits on the tailnet at
`grafana.gentoo-mine.ts.net` rather than being exposed to the world &mdash;
there&rsquo;s no login, because Tailscale decides who can reach it. A handful of
alerts watch the logging pipeline itself for the sort of thing that would
otherwise rot quietly: Loki running low on disk, ingestion stalling, or a node
that has stopped sending its logs.

I also run a second, separate Prometheus in the `lifestyle` namespace for
personal things that aren&rsquo;t really about the cluster at all &mdash; air
quality from a few [**Awair**](https://www.getawair.com/) monitors around the
flat, figures from my [**Grocy**](https://grocy.info/) home inventory, and the
state of the living-room TV.

## Claude

A good deal of this cluster is built and looked after with the help of an AI
assistant &mdash; Claude &mdash; which has a handful of its own small services
running here, in the `claude` and `claude-*` namespaces. Most of them are little
adapters that let it reach things I use day to day, like my shopping and my home
inventory. There&rsquo;s also a webhook service at `webhook.k3s.fluv.net` so that
GitHub can nudge the cluster when something happens &mdash; for example, to start
an automated review when I open a pull request.

## End-user services

We&rsquo;re running a single-user [**Mastodon**](https://joinmastodon.org/) instance on
Kubernetes. This used to run solely on my VPS, but this caused problems: it is
a disconcertingly resource-intensive Ruby program, and it meant my VPS often
ran out of RAM and fell offline halfway through an upgrade.

I&rsquo;m using a hybrid solution at the moment. The pods are running in Kubernetes,
but I&rsquo;m still using the old PostgreSQL and Redis servers that were already on
my VPS for the "important" stuff. Instead of using Kubernetes persistent volumes,
we&rsquo;re using [Google Cloud Storage](https://cloud.google.com/storage) for
user data.

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
  like Mastodon, Authentik, Argo CD, cert-manager and ingress-nginx, and
  `cluster-low` (value 100, global default) for everything else. When the VPS
  runs low on memory, low-priority pods are preempted to make room for critical
  ones
* the [**Descheduler**](https://sigs.k8s.io/descheduler) runs every five minutes;
  most workloads carry no node affinity, so placement is driven purely by
  available resources — the Pi's larger allocatable pool (~7 GB vs saraneth's
  ~1.7 GB) means the scheduler fills it first when it returns after an outage


## Costs

The Raspberry Pi cost me £90 (2023), and its 256GB MicroSD card cost £30 (2025).
Google Cloud storage, used for Mastodon,  costs me about £1 a month.
A base plan on my VPS costs £65 a year, and I pay extra for some additional RAM.

I&rsquo;m using the personal Tailscale plan, which is free.
