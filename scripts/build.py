#!/usr/bin/env python3
"""Build data/plans.json from providers' own PUBLIC pricing APIs.

Every number here comes from a live, unauthenticated vendor endpoint.
Nothing is hand-typed. If an endpoint fails, that provider is dropped from
the build rather than served stale -- see `errors` in the output.
"""
import json, sys, urllib.request, datetime, os

UA = {"User-Agent": "vps-price-index/1.0 (+https://github.com/p32929/vps-price-index)"}
OUT = os.path.join(os.path.dirname(__file__), "..", "docs", "plans.json")

SOURCES = {
    "Vultr":     "https://api.vultr.com/v2/plans?type=vc2&per_page=500",
    "Akamai":    "https://api.linode.com/v4/linode/types",
    "Scaleway":  "https://api.scaleway.com/instance/v1/zones/fr-par-1/products/servers",
    "Lightsail": "https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonLightsail/current/index.json",
    "_fx":       "https://api.frankfurter.app/latest?from=EUR&to=USD",
}

def get(url, timeout=90):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)

def row(provider, plan, vcpu, ram_gb, disk_gb, transfer_tb, price, cur, note=""):
    return {"provider": provider, "plan": plan, "vcpu": vcpu,
            "ram_gb": round(ram_gb, 2), "disk_gb": round(disk_gb),
            "transfer_tb": round(transfer_tb, 2) if transfer_tb else 0,
            "price": round(price, 2), "currency": cur, "note": note}

def vultr(d):
    out = []
    for p in d["plans"]:
        if p["monthly_cost"] <= 0:
            continue  # free/promo tier, not a buyable plan
        out.append(row("Vultr", p["id"], p["vcpu_count"], p["ram"] / 1024,
                       p["disk"], p["bandwidth"] / 1024, p["monthly_cost"], "USD",
                       p.get("cpu_vendor", "")))
    return out

def akamai(d):
    out = []
    for t in d["data"]:
        m = (t.get("price") or {}).get("monthly")
        if not m or t.get("gpus") or t["class"] in ("gpu", "metal", "accelerated"):
            continue  # premium/metal types publish a null monthly price
        out.append(row("Akamai (Linode)", t["label"], t["vcpus"], t["memory"] / 1024,
                       t["disk"] / 1024, t["transfer"] / 1024,
                       m, "USD", t["class"]))
    return out

def scaleway(d):
    out = []
    for name, s in d["servers"].items():
        if s.get("gpu") or not s.get("monthly_price"):
            continue
        disk = s.get("volumes_constraint", {}).get("min_size", 0) / 1e9
        out.append(row("Scaleway", name, s["ncpus"], s["ram"] / 1e9, disk,
                       0, s["monthly_price"], "EUR", s.get("arch", "")))
    return out

def lightsail(d):
    """AWS publishes hourly bundle prices; 730h = AWS's own monthly convention."""
    best = {}
    for sku, p in d["products"].items():
        a = p["attributes"]
        if p["productFamily"] != "Lightsail Instance":
            continue
        if a.get("operatingSystem") != "Linux" or a.get("location") != "US East (N. Virginia)":
            continue
        if "IPv6" in a.get("groupDescription", ""):
            continue
        terms = d["terms"]["OnDemand"].get(sku)
        if not terms:
            continue
        dim = next(iter(next(iter(terms.values()))["priceDimensions"].values()))
        hourly = float(dim["pricePerUnit"]["USD"])
        if hourly <= 0:
            continue
        ram = float(a["memory"].rstrip("GB"))
        key = (a["vcpu"], a["memory"], a["storage"])
        monthly = hourly * 730
        if key not in best or monthly < best[key]["price"]:
            best[key] = row("AWS Lightsail", a["usagetype"].split(":")[-1] + " bundle",
                            int(a["vcpu"]), ram, float(a["storage"].rstrip("GB")),
                            0, monthly, "USD", "us-east-1, Linux")
    return list(best.values())

PARSERS = {"Vultr": vultr, "Akamai": akamai, "Scaleway": scaleway, "Lightsail": lightsail}

def main():
    plans, errors, sources = [], {}, {}
    fx = None
    try:
        fxd = get(SOURCES["_fx"], 30)
        fx = {"EUR_USD": fxd["rates"]["USD"], "date": fxd["date"], "source": SOURCES["_fx"]}
    except Exception as e:
        errors["_fx"] = str(e)

    for key, url in SOURCES.items():
        if key == "_fx":
            continue
        try:
            got = PARSERS[key](get(url))
            if not got:
                raise ValueError("parser returned 0 plans")
            plans += got
            sources[key] = url
        except Exception as e:
            errors[key] = f"{type(e).__name__}: {e}"
            print(f"!! {key} FAILED -> dropped: {e}", file=sys.stderr)

    # one comparable column, with the rate and its date published alongside
    for p in plans:
        r = fx["EUR_USD"] if (p["currency"] == "EUR" and fx) else 1.0
        p["usd"] = round(p["price"] * r, 2) if p["currency"] in ("USD", "EUR") else None
        if p["usd"] and p["ram_gb"]:
            p["usd_per_gb_ram"] = round(p["usd"] / p["ram_gb"], 2)

    plans.sort(key=lambda p: (p["usd"] is None, p["usd"] or 0))
    doc = {
        "generated_utc": datetime.datetime.now(datetime.timezone.utc)
                                  .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "plan_count": len(plans), "fx": fx, "sources": sources,
        "errors": errors, "plans": plans,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(doc, f, indent=1)
    print(f"wrote {len(plans)} plans from {len(sources)} providers -> {OUT}")
    if errors:
        print("errors:", errors)
    return 0 if sources else 1

if __name__ == "__main__":
    sys.exit(main())
