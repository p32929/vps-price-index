#!/usr/bin/env python3
"""Self-check on the built dataset. Run: python3 scripts/test_build.py"""
import json, os, sys
d = json.load(open(os.path.join(os.path.dirname(__file__), "..", "docs", "plans.json")))
p = d["plans"]
assert d["plan_count"] == len(p), "plan_count disagrees with the list"
assert len(p) > 40, f"only {len(p)} plans - a source probably broke silently"
assert len({x["provider"] for x in p}) >= 3, "fewer than 3 providers survived"
assert not d["errors"], f"sources failed: {d['errors']}"
for x in p:
    assert x["vcpu"] >= 1 and x["ram_gb"] > 0, f"bad specs: {x}"
    assert x["price"] > 0, f"non-positive price: {x}"
    assert x["currency"] in ("USD", "EUR"), f"unhandled currency: {x}"
    if x["usd"] is not None:
        assert 0 < x["usd"] < 100000, f"implausible usd: {x}"
        # the comparable column must actually be the converted native price
        rate = d["fx"]["EUR_USD"] if x["currency"] == "EUR" else 1.0
        assert abs(x["usd"] - x["price"] * rate) < 0.02, f"usd != price*fx: {x}"
assert p == sorted(p, key=lambda q: (q["usd"] is None, q["usd"] or 0)), "not sorted by usd"
# known-good anchors: if these drift, the parsers have silently changed meaning
nanode = [x for x in p if x["plan"] == "Nanode 1GB"]
assert nanode and nanode[0]["usd"] == 5.0, f"Linode Nanode 1GB should be $5/mo, got {nanode}"
print(f"PASS - {len(p)} plans, {len({x['provider'] for x in p})} providers, fx {d['fx']['EUR_USD']} @ {d['fx']['date']}")
