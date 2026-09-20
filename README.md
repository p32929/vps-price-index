# VPS Price Index

**Live cloud server prices, pulled from the providers' own public APIs. Nothing is hand-typed.**

👉 **[p32929.github.io/vps-price-index](https://p32929.github.io/vps-price-index/)** — sortable, filterable, 120 plans
📦 **[`docs/plans.json`](docs/plans.json)** — the raw dataset, CC0, use it in your own tooling

---

Every "cheapest VPS" comparison you find is a blog post someone typed by hand in 2023 and never touched again. The prices are wrong, the plans don't exist any more, and there is no way to tell which parts went stale.

This is the opposite. A script hits each provider's **public, unauthenticated pricing endpoint**, normalises the result, and publishes it. It runs every day. You can run it yourself in about four seconds:

```bash
python3 scripts/build.py      # no API keys, no dependencies, no account
python3 scripts/test_build.py # self-check before you trust the output
```

## Where the numbers come from

| Provider | Endpoint (open it, check the number yourself) |
|---|---|
| Vultr | `https://api.vultr.com/v2/plans?type=vc2` |
| Akamai (Linode) | `https://api.linode.com/v4/linode/types` |
| Scaleway | `https://api.scaleway.com/instance/v1/zones/fr-par-1/products/servers` |
| AWS Lightsail | `https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonLightsail/current/index.json` |
| EUR→USD rate | `https://api.frankfurter.app/latest?from=EUR&to=USD` |

All five are public. None need a key. That is the whole point — you do not have to trust this repo, you can check any row at the source in one click.

## The rules this thing holds itself to

- **No hand-typed prices.** If it is in the table, a provider's API said it, today.
- **A broken source is dropped, never served stale.** If a provider's endpoint fails or its shape changes, that provider disappears from the build and the failure is recorded in `errors` inside `plans.json`. A silently wrong number is worse than a missing one.
- **The FX rate is published with its date.** Scaleway quotes EUR. The `$` column is a conversion, not a price, so the rate and the day it was taken are printed on the page and stored in the JSON. Native price is shown next to it.
- **The conventions are stated, not hidden.** AWS publishes Lightsail hourly; the monthly figure is hourly × 730, which is AWS's own convention, Linux, us-east-1. Linode/Vultr/Scaleway publish monthly directly.
- **Providers with no affiliate programme are listed anyway.** AWS Lightsail cannot be monetised here and is in the table regardless, because a comparison that quietly omits the options that do not pay is not a comparison.

## `plans.json`

```json
{
  "generated_utc": "...", "plan_count": 120,
  "fx": {"EUR_USD": 1.146, "date": "2026-09-18", "source": "..."},
  "sources": {"Vultr": "...", "Akamai": "...", "Scaleway": "...", "Lightsail": "..."},
  "errors": {},
  "plans": [
    {"provider":"Akamai (Linode)","plan":"Nanode 1GB","vcpu":1,"ram_gb":1.0,
     "disk_gb":25,"transfer_tb":0.98,"price":5.0,"currency":"USD",
     "note":"nanode","usd":5.0,"usd_per_gb_ram":5.0}
  ]
}
```

Dataset is **CC0** — take it, no attribution needed. Code is MIT.

## Affiliate disclosure

Provider links live in one file, [`docs/partners.json`](docs/partners.json). Each one records whether it is an affiliate link and which programme it belongs to.

**Right now every link in this repo is a plain, untracked link to the provider's own pricing page — there are no affiliate links in it at all.** If that changes, the flag in `partners.json` flips to `true`, the link is marked `ad` in the table, it gets `rel="sponsored nofollow"`, and a disclosure banner appears at the top of the page. You will be able to see exactly which rows are monetised by reading one small JSON file, and `git log` will show you the day it happened.

Affiliate links could never change a price in the table anyway, because no human hand touches the prices — they come from the APIs above.

For what it is worth, here is the honest state of every programme behind the four providers, checked 2026-09-20:

| Provider | Programme | Pays |
|---|---|---|
| Vultr | Affiliate programme, ~$10–100 one-time per qualified sale, 30-day cookie | **cash** |
| Akamai (Linode) | Referral programme, "give $100 / get $25" — and you must spend $25 yourself to even activate the link | account credit only |
| Scaleway | No self-serve affiliate programme exists; customers have an [open feature request](https://feature-request.scaleway.com/posts/129/affiliate-program) asking for one | nothing |
| AWS Lightsail | No consumer affiliate programme | nothing |

So three of the four providers here can never be monetised, and they are in the table anyway.

## Contributing

The useful contribution is **another provider with a public, unauthenticated pricing endpoint**. Add a parser to `scripts/build.py` that returns `row(...)` dicts and register it in `SOURCES`/`PARSERS`. That is the whole interface.

Known non-starters, so you do not waste an evening:

- **Hetzner** — `api.hetzner.cloud/v1/pricing` returns `401 token is required`. Excellent prices, no open catalogue.
- **DigitalOcean** — `api.digitalocean.com/v2/sizes` needs a bearer token.
- **OVHcloud** — `api.ovh.com/v1/order/catalog/public/vps?ovhSubsidiary=GB` is genuinely public (197 plans) but specs are not machine-readable: some plans encode vCPU/RAM in the `planCode`, others hide them in a `blobs.commercial` marketing feature list and some have `blobs: null`. Prices are in `pricings[].price` at 1e8 per unit. Doable, but it needs a careful parser, not a quick one — PRs very welcome.
