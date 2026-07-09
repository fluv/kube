# slipway

Renders recorded household data and nearby public map to-do lists
(OpenStreetMap notes, Wikidata items without an image) as a short daily
list of concrete prompts. Source in [fluv/slipway](https://github.com/fluv/slipway).

Exposed tailnet-only at `slipway.gentoo-mine.ts.net` via the Tailscale
operator ingress. Scraped by the lifestyle Prometheus (`/metrics`).

## Secrets (created out-of-band, not in git — both optional)

Both secret references are `optional: true`: the app comes up healthy with
neither present. Without `grocy-api-key` the Grocy source shows as
unavailable on the page; without `slipway-home` the map sources and
forecast centre on a neutral city-centre placeholder baked into the image.

To enable full behaviour later:

```sh
kubectl create secret generic grocy-api-key -n slipway \
  --from-literal=GROCY_APIKEY_VALUE=<grocy api key>

kubectl create secret generic slipway-home -n slipway \
  --from-literal=SLIPWAY_HOME=<lat,lon>

kubectl rollout restart deployment/slipway -n slipway
```

`grocy-api-key` mirrors the secret of the same name in `claude-grocy`
(same key name, so the value can be copied across). `slipway-home` is the
coordinate the map sources and forecast centre on — deployment
configuration handled like a secret.

## Image

`ghcr.io/fluv/slipway`, built multi-arch (arm64 + amd64) by GitHub Actions
in the source repo. The GHCR package must be public for the cluster to pull
without an `imagePullSecret` — same pattern as `claude-grocy` and
`claude-vestibule`.
