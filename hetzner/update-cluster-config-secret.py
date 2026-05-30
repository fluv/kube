#!/usr/bin/env python3
"""
Render cloud-init-template.yaml into the HCLOUD_CLUSTER_CONFIG JSON expected
by the hetzner cluster-autoscaler (v9.x+ chart, post-HCLOUD_CLOUD_INIT format).

Reads tailscale auth key and k3s token from the existing hcloud-init-data
secret (data.ts-auth-key, data.k3s-token), substitutes them into the template,
and writes the resulting cluster-config JSON to data.cluster-config of the
same secret.

Per-pool labels include kubernetes.io/os=linux so the autoscaler's template
scheduling check passes for pods that nodeSelect on it (fluv/kube#258).

Never prints secret values. Usage:
    python3 update-cluster-config-secret.py
    python3 update-cluster-config-secret.py --dry-run
"""
import argparse, base64, json, subprocess, sys
from pathlib import Path

TEMPLATE = Path(__file__).parent / "cloud-init-template.yaml"
SECRET_NAME = "hcloud-init-data"
SECRET_NS = "kube-system"
IMAGE = "ubuntu-24.04"
# Hetzner network ID for k3s-private (10.30.0.0/16). Including this in
# nodeConfigs ensures the network is attached at server-creation time, not as
# a post-creation step. Post-creation attachment causes the Hetzner SDN to
# skip initialising inbound routing for the node's private IP, breaking
# flannel VxLAN from other nodes (confirmed on hetz-8gb, 2026-05-30).
NETWORK_ID = 12239723

POOLS = [
    {"name": "hetz-4gb-nbg1"},
    {"name": "hetz-4gb-hel1"},
    {"name": "hetz-8gb-hel1"},
    {"name": "hetz-16gb-hel1"},
    {"name": "hetz-32gb-hel1"},
]

LABELS = {
    "kubernetes.io/os": "linux",
    # Required by hcloud-csi nodeSelector; CCM is not deployed so we set it here.
    "instance.hetzner.cloud/provided-by": "cloud",
}


def kubectl(*args, **kwargs):
    r = subprocess.run(["kubectl", *args], capture_output=True, text=True, **kwargs)
    if r.returncode != 0:
        print(f"kubectl error: {r.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    return r.stdout.strip()


def get_secret_values():
    raw = kubectl("get", "secret", "-n", SECRET_NS, SECRET_NAME, "-o", "json")
    data = json.loads(raw)["data"]
    if "ts-auth-key" not in data or "k3s-token" not in data:
        print("ERROR: secret missing ts-auth-key or k3s-token", file=sys.stderr)
        sys.exit(1)
    ts = base64.b64decode(data["ts-auth-key"]).decode().strip()
    k3s = base64.b64decode(data["k3s-token"]).decode().strip()
    return ts, k3s


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true",
                   help="Print rendered cluster-config JSON (with secrets redacted) without applying")
    args = p.parse_args()

    ts_key, k3s_token = get_secret_values()

    template = TEMPLATE.read_text()
    cloud_init = template.replace("__TAILSCALE_AUTH_KEY__", ts_key) \
                         .replace("__K3S_TOKEN__", k3s_token)

    config = {
        "imagesForArch": {"amd64": IMAGE},
        "nodeConfigs": {
            pool["name"]: {
                "cloudInit": cloud_init,
                "labels": LABELS,
                "networks": [NETWORK_ID],
            }
            for pool in POOLS
        },
    }
    config_json = json.dumps(config, indent=2)

    if args.dry_run:
        # Redact secrets before printing
        redacted = config_json.replace(ts_key, "<TS_KEY_REDACTED>") \
                              .replace(k3s_token, "<K3S_TOKEN_REDACTED>")
        print(redacted)
        return

    # HCLOUD_CLUSTER_CONFIG must arrive at the autoscaler as base64-encoded JSON.
    # k8s decodes /data values once when mounting as env var, so double-encode:
    # outer for the secret wire format, inner for what the autoscaler parses.
    inner = base64.b64encode(config_json.encode()).decode()
    value = base64.b64encode(inner.encode()).decode()
    # Use add+replace to handle both first-time creation and updates
    test_get = kubectl("get", "secret", "-n", SECRET_NS, SECRET_NAME,
                       "-o", "jsonpath={.data.cluster-config}")
    op = "replace" if test_get else "add"
    patch = json.dumps([{"op": op, "path": "/data/cluster-config", "value": value}])

    print(f"Patching {SECRET_NS}/{SECRET_NAME} (op={op}, key=cluster-config)...")
    kubectl("patch", "secret", "-n", SECRET_NS, SECRET_NAME,
            "--type=json", f"--patch={patch}")
    print("Done.")


if __name__ == "__main__":
    main()
