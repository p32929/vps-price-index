#!/usr/bin/env python3
"""Build docs/changes.json + docs/changes.html: a dated record of what actually
moved between two daily snapshots of docs/plans.json.

Derived from git history every run, so it is self-healing and needs no state
file -- but the workflow must check out with `fetch-depth: 0`.

Run: python3 scripts/changes.py          (build)
     python3 scripts/changes.py --test   (self-check, no network, no git)
"""
import json, os, subprocess, sys, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(HERE, "..", "docs")
PLANS_PATH = "docs/plans.json"


def snapshots():
    """Every committed version of plans.json, oldest first."""
    log = subprocess.check_output(
        ["git", "log", "--format=%H %cI", "--", PLANS_PATH],
        cwd=os.path.join(HERE, ".."), text=True).strip()
    out = []
    for line in reversed([l for l in log.split("\n") if l.strip()]):
        sha, iso = line.split()
        blob = subprocess.check_output(
            ["git", "show", f"{sha}:{PLANS_PATH}"],
            cwd=os.path.join(HERE, ".."), text=True)
        out.append((sha, iso, json.loads(blob)))
    return out


def diff(old, new):
    """What changed between two plans.json documents.

    Native price only -- a USD column that moved purely because the euro moved
    is an FX event, not a price cut, and saying otherwise would be a lie.
    """
    o = {(p["provider"], p["plan"]): p for p in old["plans"]}
    n = {(p["provider"], p["plan"]): p for p in new["plans"]}
    moves = []
    for k in sorted(n.keys() & o.keys()):
        a, b = o[k]["price"], n[k]["price"]
        if a != b:
            moves.append({"provider": k[0], "plan": k[1], "currency": n[k]["currency"],
                          "from": a, "to": b, "pct": round((b - a) / a * 100, 1) if a else None})
    added = [{"provider": k[0], "plan": k[1], "price": n[k]["price"],
              "currency": n[k]["currency"]} for k in sorted(n.keys() - o.keys())]
    removed = [{"provider": k[0], "plan": k[1], "price": o[k]["price"],
                "currency": o[k]["currency"]} for k in sorted(o.keys() - n.keys())]
    fx_old = (old.get("fx") or {}).get("EUR_USD")
    fx_new = (new.get("fx") or {}).get("EUR_USD")
    fx = {"from": fx_old, "to": fx_new, "date": (new.get("fx") or {}).get("date")} \
        if fx_old != fx_new else None
    return {"moves": moves, "added": added, "removed": removed, "fx": fx}


def build():
    snaps = snapshots()
    days = []
    for (psha, piso, pdoc), (sha, iso, doc) in zip(snaps, snaps[1:]):
        d = diff(pdoc, doc)
        if not (d["moves"] or d["added"] or d["removed"] or d["fx"]):
            continue          # nothing moved; don't invent a headline
        d.update({"date": iso[:10], "utc": iso, "sha": sha,
                  "plan_count": doc["plan_count"]})
        days.append(d)
    days.reverse()
    latest = snaps[-1]
    out = {
        "generated_utc": datetime.datetime.now(datetime.timezone.utc)
                                  .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "snapshots": len(snaps),
        "first_snapshot": snaps[0][1][:10],
        "latest_snapshot": latest[1][:10],
        "plan_count": latest[2]["plan_count"],
        "days": days,
    }
    with open(os.path.join(DOCS, "changes.json"), "w") as f:
        json.dump(out, f, indent=1)
    with open(os.path.join(DOCS, "changes.html"), "w") as f:
        f.write(render(out))
    print(f"wrote {len(days)} dated change entries from {len(snaps)} snapshots")
    return 0


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(d):
    rows = []
    for day in d["days"]:
        items = []
        for m in day["moves"]:
            arrow = "▲" if m["to"] > m["from"] else "▼"
            cls = "up" if m["to"] > m["from"] else "down"
            items.append(f'<li><span class="prov">{esc(m["provider"])}</span> '
                         f'<span class="plan">{esc(m["plan"])}</span> '
                         f'<span class="{cls}">{arrow} {m["from"]} → {m["to"]} {esc(m["currency"])}'
                         f'{f" ({m['pct']:+}%)" if m["pct"] is not None else ""}</span></li>')
        for a in day["added"]:
            items.append(f'<li><span class="new">NEW</span> <span class="prov">{esc(a["provider"])}</span> '
                         f'<span class="plan">{esc(a["plan"])}</span> at {a["price"]} {esc(a["currency"])}</li>')
        for r in day["removed"]:
            items.append(f'<li><span class="gone">GONE</span> <span class="prov">{esc(r["provider"])}</span> '
                         f'<span class="plan">{esc(r["plan"])}</span> was {r["price"]} {esc(r["currency"])}</li>')
        if day["fx"]:
            items.append(f'<li class="fxrow">EUR/USD {day["fx"]["from"]} → {day["fx"]["to"]} '
                         f'(rate dated {esc(day["fx"]["date"])}) — every euro-priced plan\'s $ column '
                         f'moved with it. <b>No provider changed its own price.</b></li>')
        rows.append(f'<section class="day"><h2>{esc(day["date"])}</h2>'
                    f'<p class="sub">{len(day["moves"])} price change(s), {len(day["added"])} new plan(s), '
                    f'{len(day["removed"])} withdrawn · {day["plan_count"]} plans tracked · '
                    f'<a href="https://github.com/p32929/vps-price-index/commit/{esc(day["sha"])}">'
                    f'snapshot {esc(day["sha"][:7])}</a></p><ul>{"".join(items)}</ul></section>')
    body = "".join(rows) or '<p class="sub">Nothing has moved since tracking began.</p>'
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>VPS price changes — a dated record of who raised or cut prices</title>
<meta name="description" content="A dated record of every VPS price change: who raised prices, who cut them, which plans appeared and which were withdrawn. Rebuilt daily from each provider's own public pricing API.">
<link rel="canonical" href="https://p32929.github.io/vps-price-index/changes.html">
<style>
:root{{--bg:#0d1117;--panel:#161b22;--line:#30363d;--fg:#e6edf3;--dim:#8b949e;--acc:#3fb950;--acc2:#58a6ff}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}}
a{{color:var(--acc2)}}
.wrap{{max-width:900px;margin:0 auto;padding:28px 18px 64px}}
h1{{font-size:27px;margin:0 0 6px;letter-spacing:-.4px}}
h2{{font-size:17px;margin:0 0 4px;font-variant-numeric:tabular-nums}}
.sub{{color:var(--dim);margin:0 0 18px;font-size:14px}}
.badge{{display:inline-block;background:var(--panel);border:1px solid var(--line);border-radius:999px;padding:3px 11px;font-size:12px;color:var(--dim);margin:0 6px 14px 0}}
.badge b{{color:var(--acc)}}
.day{{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:14px 16px;margin:0 0 14px}}
.day .sub{{margin:0 0 10px;font-size:12.5px}}
ul{{margin:0;padding-left:18px}}
li{{margin:3px 0;font-size:14px}}
.prov{{color:var(--dim);font-size:12.5px}}
.plan{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.5px}}
.up{{color:#f85149;font-weight:600}}
.down{{color:var(--acc);font-weight:600}}
.new{{color:var(--acc);font-size:10px;border:1px solid var(--acc);border-radius:4px;padding:0 4px}}
.gone{{color:#d29922;font-size:10px;border:1px solid #d29922;border-radius:4px;padding:0 4px}}
.fxrow{{color:var(--dim)}}
footer{{margin-top:26px;color:var(--dim);font-size:12.5px;line-height:1.8}}
</style>
</head>
<body>
<div class="wrap">
<h1>VPS price changes</h1>
<p class="sub">Who raised prices, who cut them, which plans appeared and which quietly disappeared — dated, and taken from
a daily snapshot of each provider's <b>own public pricing API</b>. <a href="./">Back to the price index →</a></p>
<span class="badge">tracking since <b>{esc(d['first_snapshot'])}</b></span>
<span class="badge"><b>{d['snapshots']}</b> daily snapshots</span>
<span class="badge"><b>{d['plan_count']}</b> plans watched</span>
<span class="badge">latest <b>{esc(d['latest_snapshot'])}</b></span>
{body}
<footer>
Only a change in the provider's <b>own</b> price counts as a price change here. If the dollar column moved because the
euro moved, it is listed as an FX line and labelled as one — a comparison table that calls that a "price cut" is lying to you.<br>
Rebuilt daily by GitHub Actions from <a href="https://github.com/p32929/vps-price-index">the open-source build script</a>;
every entry links to the exact commit it was computed from, so you can check it.<br>
Generated {esc(d['generated_utc'])}.
</footer>
</div>
</body>
</html>
"""


def selftest():
    a = {"plans": [{"provider": "V", "plan": "a", "price": 5.0, "currency": "USD"},
                   {"provider": "V", "plan": "b", "price": 10.0, "currency": "USD"}],
         "fx": {"EUR_USD": 1.1, "date": "2026-01-01"}}
    b = {"plans": [{"provider": "V", "plan": "a", "price": 6.0, "currency": "USD"},
                   {"provider": "V", "plan": "c", "price": 3.0, "currency": "EUR"}],
         "fx": {"EUR_USD": 1.2, "date": "2026-01-02"}}
    d = diff(a, b)
    assert d["moves"] == [{"provider": "V", "plan": "a", "currency": "USD",
                           "from": 5.0, "to": 6.0, "pct": 20.0}], d["moves"]
    assert [x["plan"] for x in d["added"]] == ["c"], d["added"]
    assert [x["plan"] for x in d["removed"]] == ["b"], d["removed"]
    assert d["fx"] == {"from": 1.1, "to": 1.2, "date": "2026-01-02"}, d["fx"]
    assert diff(a, a) == {"moves": [], "added": [], "removed": [], "fx": None}
    html = render({"generated_utc": "x", "snapshots": 2, "first_snapshot": "2026-01-01",
                   "latest_snapshot": "2026-01-02", "plan_count": 2,
                   "days": [dict(d, date="2026-01-02", utc="", sha="deadbeefcafe", plan_count=2)]})
    assert "5.0 → 6.0 USD (+20.0%)" in html and "NEW" in html and "GONE" in html
    print("PASS - changes.py diff + render")
    return 0


if __name__ == "__main__":
    sys.exit(selftest() if "--test" in sys.argv else build())
