#!/usr/bin/env python3
"""
BYD Australia 门店监控 — 抓取脚本

数据来源：https://bydautomotive.com.au/find-us
该页面把全部门店以 JavaScript 变量 `LocationsArr = [...]` 内嵌在 HTML 中，
本脚本直接解析该数组，筛出销售点（pinType == "pickup"，即 Experience Centre 类），
写出 data/locations.json，并把本次快照与上一次比较后追加到 data/history.json。

用法：
    python3 scrape_byd.py [--out DIR]          # 默认 DIR = ./site/data
    python3 scrape_byd.py --history PATH       # 指定已有 history.json（用于与上次比较）
"""
import argparse
import datetime as dt
import json
import pathlib
import re
import sys
import urllib.request

URL = "https://bydautomotive.com.au/find-us"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
STATES = ["NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT"]
MAX_HISTORY = 400  # 条快照，约一年多的每日记录


def fetch_html() -> str:
    req = urllib.request.Request(URL, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", errors="ignore")


def parse_locations(html: str) -> list[dict]:
    m = re.search(r"LocationsArr\s*=\s*(\[\{.*?\}\]);", html, re.S)
    if not m:
        raise RuntimeError("页面中未找到 LocationsArr —— 官网结构可能已变更")
    return json.loads(m.group(1))


def s(v) -> str:
    return str(v).strip() if v not in (None, "") else ""


def norm_badge(b: str) -> str:
    """统一官网不一致的类型写法：Coming-soon / Coming Soon、Center / Centre 等。"""
    key = re.sub(r"[\s\-_]+", "", b).lower()
    table = {
        "comingsoon": "Coming Soon",
        "experiencecentre": "Experience Centre",
        "experiencecenter": "Experience Centre",
        "popupexperience": "Pop-up Experience",
        "testdrive&deliverycentre": "Test Drive & Delivery Centre",
        "testdrive&deliverycenter": "Test Drive & Delivery Centre",
    }
    return table.get(key, b or "Experience Centre")


def slim(loc: dict) -> dict:
    return {
        "id": loc.get("designLocationId"),
        "name": s(loc.get("name")),
        "badge": norm_badge(s(loc.get("mapBadge"))),
        "address": s(loc.get("address")),
        "city": s(loc.get("city")),
        "state": s(loc.get("state")).upper(),
        "postcode": s(loc.get("postcode")),
        "phone": s(loc.get("phone")),
        "website": s(loc.get("website")),
        "lat": loc.get("lat"),
        "lng": loc.get("lng"),
    }


def build_snapshot(raw: list[dict]) -> dict:
    sales = [slim(x) for x in raw if x.get("pinType") == "pickup"]
    sales.sort(key=lambda x: (STATES.index(x["state"]) if x["state"] in STATES else 99, x["name"]))
    by_state = {s: sum(1 for x in sales if x["state"] == s) for s in STATES}
    by_badge: dict[str, int] = {}
    for x in sales:
        by_badge[x["badge"] or "Experience Centre"] = by_badge.get(x["badge"] or "Experience Centre", 0) + 1
    all_types: dict[str, int] = {}
    for x in raw:
        all_types[x.get("pinType") or "?"] = all_types.get(x.get("pinType") or "?", 0) + 1
    now = dt.datetime.now(dt.timezone.utc)
    return {
        "source": URL,
        "fetched_at_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fetched_at_aest": (now + dt.timedelta(hours=10)).strftime("%Y-%m-%d %H:%M AEST"),
        "count": len(sales),
        "by_state": by_state,
        "by_badge": by_badge,
        "all_pin_types": all_types,  # 官网全部点位类型计数（含服务中心、钣喷等），供参考
        "locations": sales,
    }


def diff(prev: dict | None, cur: dict) -> dict:
    if not prev:
        return {"added": [], "removed": [], "renamed": []}
    p = {x["id"]: x for x in prev.get("locations", [])}
    c = {x["id"]: x for x in cur["locations"]}
    added = [c[i] for i in c if i not in p]
    removed = [p[i] for i in p if i not in c]
    renamed = [
        {"id": i, "from": p[i]["name"], "to": c[i]["name"]}
        for i in c if i in p and p[i]["name"] != c[i]["name"]
    ]
    return {
        "added": [{"id": x["id"], "name": x["name"], "state": x["state"], "city": x["city"]} for x in added],
        "removed": [{"id": x["id"], "name": x["name"], "state": x["state"], "city": x["city"]} for x in removed],
        "renamed": renamed,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="site/data")
    ap.add_argument("--history", default=None, help="已有 history.json 路径（默认 OUT/history.json）")
    ap.add_argument("--prev", default=None, help="上一次 locations.json 路径（默认 OUT/locations.json）")
    a = ap.parse_args()

    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    hist_path = pathlib.Path(a.history) if a.history else out / "history.json"
    prev_path = pathlib.Path(a.prev) if a.prev else out / "locations.json"

    prev = json.loads(prev_path.read_text()) if prev_path.exists() else None
    history = json.loads(hist_path.read_text()) if hist_path.exists() else []

    html = fetch_html()
    raw = parse_locations(html)
    cur = build_snapshot(raw)
    d = diff(prev, cur)

    history.append({
        "date": cur["fetched_at_utc"][:10],
        "fetched_at_utc": cur["fetched_at_utc"],
        "count": cur["count"],
        "by_state": cur["by_state"],
        **d,
    })
    # 同一天多次运行只保留最后一次
    dedup: dict[str, dict] = {}
    for h in history:
        dedup[h["date"]] = h
    history = sorted(dedup.values(), key=lambda h: h["date"])[-MAX_HISTORY:]

    (out / "locations.json").write_text(json.dumps(cur, ensure_ascii=False, indent=1))
    (out / "history.json").write_text(json.dumps(history, ensure_ascii=False, indent=1))

    print(f"抓取时间 {cur['fetched_at_aest']}  销售点 {cur['count']} 家  "
          f"新增 {len(d['added'])}  关闭 {len(d['removed'])}  改名 {len(d['renamed'])}")
    for s in STATES:
        print(f"  {s:<4}{cur['by_state'][s]:>4}")
    for x in d["added"]:
        print("  + 新增:", x["name"], x["state"])
    for x in d["removed"]:
        print("  - 关闭:", x["name"], x["state"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
