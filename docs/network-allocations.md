# Network Allocations

| Range | Owner | Notes |
|---|---|---|
| `10.10.0.0/16` | Hetzner private network (`k3s-private`) | hcloud-to-hcloud pod overlay (flannel VXLAN via ens10) |
| `10.10.1.0/24` | └ nbg1 subnet | |
| `10.10.2.0/24` | └ fsn1 subnet | |
| `10.10.3.0/24` | └ hel1 subnet | |
| `10.42.0.0/16` | k3s pod CIDR | flannel overlay, assigned by kube-controller |
| `10.43.0.0/16` | k3s service CIDR | ClusterIPs, assigned by kube-apiserver |
| `10.250.0.0/16` | Reserved — external use | do not allocate |
| `100.64.0.0/10` | Tailscale | control-plane traffic, cross-region access, Pi↔saraneth↔hcloud |
| `192.168.1.0/24` | Home LAN | Pi is on this network |
