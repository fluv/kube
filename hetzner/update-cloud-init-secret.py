#!/usr/bin/env python3
"""
Render cloud-init-template.yaml and apply it as the hcloud-init-data secret.

The secret has three fields:
  data.ts-auth-key  — Tailscale auth key (base64-encoded)
  data.k3s-token    — k3s node token (base64-encoded)
  data.cloud-init   — rendered cloud-init YAML, double-encoded:
                       k8s wire format wraps an inner base64 value that the
                       hcloud CCM passes directly to Hetzner's user-data API.

By default, ts-auth-key and k3s-token values are read from the existing secret
(useful when re-rendering after a template change). Pass --authkey and/or
--token to override.

Usage:
    python3 update-cloud-init-secret.py
    python3 update-cloud-init-secret.py --authkey tskey-auth-... --token K10...
    python3 update-cloud-init-secret.py --dry-run
"""
import argparse, base64, json, subprocess, sys
from pathlib import Path

TEMPLATE = Path(__file__).parent / "cloud-init-template.yaml"
SECRET_NAME = "hcloud-init-data"
SECRET_NS = "kube-system"


def kubectl(*args):
    r = subprocess.run(["kubectl", *args], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"kubectl error: {r.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    return r.stdout.strip()


def get_existing_values():
    """Read ts-auth-key and k3s-token from the separate secret fields."""
    ts_raw  = kubectl("get", "secret", "-n", SECRET_NS, SECRET_NAME,
                      "-o", "jsonpath={.data.ts-auth-key}")
    k3s_raw = kubectl("get", "secret", "-n", SECRET_NS, SECRET_NAME,
                      "-o", "jsonpath={.data.k3s-token}")
    if not ts_raw or not k3s_raw:
        print("ERROR: ts-auth-key or k3s-token not found in secret", file=sys.stderr)
        sys.exit(1)
    ts_key    = base64.b64decode(ts_raw).decode()
    k3s_token = base64.b64decode(k3s_raw).decode()
    return ts_key, k3s_token


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--authkey", help="Tailscale auth key (default: read from existing secret)")
    p.add_argument("--token", help="k3s node token (default: read from existing secret)")
    p.add_argument("--dry-run", action="store_true", help="Print rendered cloud-init without applying")
    args = p.parse_args()

    if args.authkey and args.token:
        ts_key, k3s_token = args.authkey, args.token
    else:
        print("Reading existing values from secret...")
        existing_ts, existing_k3s = get_existing_values()
        ts_key    = args.authkey or existing_ts
        k3s_token = args.token   or existing_k3s

    template = TEMPLATE.read_text()
    rendered = template.replace("__TAILSCALE_AUTH_KEY__", ts_key).replace("__K3S_TOKEN__", k3s_token)

    if args.dry_run:
        print(rendered)
        return

    # data.cloud-init: inner base64 is what hcloud CCM passes to Hetzner user-data;
    # outer base64 is the k8s wire format.
    cloud_init_value = base64.b64encode(
        base64.b64encode(rendered.encode())
    ).decode()
    ts_value  = base64.b64encode(ts_key.encode()).decode()
    k3s_value = base64.b64encode(k3s_token.encode()).decode()

    patch = json.dumps([
        {"op": "replace", "path": "/data/cloud-init",  "value": cloud_init_value},
        {"op": "replace", "path": "/data/ts-auth-key", "value": ts_value},
        {"op": "replace", "path": "/data/k3s-token",   "value": k3s_value},
    ])

    print(f"Patching {SECRET_NS}/{SECRET_NAME}...")
    kubectl("patch", "secret", "-n", SECRET_NS, SECRET_NAME,
            "--type=json", f"--patch={patch}")
    print("Done.")


if __name__ == "__main__":
    main()
