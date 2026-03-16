#!/usr/bin/env python3
"""Discord webhook that posts item prices from poe.ninja (Mirage league)."""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import requests

LEAGUE = os.environ.get('LEAGUE', 'Mirage')
BASE_URL = "https://poe.ninja/api/data"
EXCHANGE_URL = "https://poe.ninja/poe1/api/economy/exchange/current/details"
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

NINJA_URL = f"https://poe.ninja/economy/{LEAGUE.lower()}"

CURRENCY_ITEMS = {
    "divine-orb": ("Divine Orb", f"{NINJA_URL}/currency/divine-orb"),
    "mirror-of-kalandra": ("Mirror of Kalandra", f"{NINJA_URL}/currency/mirror-of-kalandra"),
    "mirror-shard": ("Mirror Shard", f"{NINJA_URL}/currency/mirror-shard"),
    "hinekoras-lock": ("Hinekora's Lock", f"{NINJA_URL}/currency/hinekoras-lock"),
}

UNIQUE_ITEMS = {
    "Headhunter": f"{NINJA_URL}/unique-accessories/headhunter-leather-belt",
    "Mageblood": f"{NINJA_URL}/unique-accessories/mageblood-heavy-belt",
}

def fetch_json(url):
    resp = requests.get(url, headers={"User-Agent": "ExilenceCE-PriceBot/1.0"})
    resp.raise_for_status()
    return resp.json()

# Items that should display in divine rather than chaos
DIVINE_DISPLAY = {"Mirror of Kalandra", "Mirror Shard", "Hinekora's Lock"}

def get_currency_data():
    results = {}
    for slug, (name, url) in CURRENCY_ITEMS.items():
        data = fetch_json(f"{EXCHANGE_URL}?league={LEAGUE}&type=Currency&id={slug}")
        pairs = {p["id"]: p for p in data.get("pairs", [])}

        chaos_pair = pairs.get("chaos", {})
        divine_pair = pairs.get("divine", {})

        entry = {"url": url}
        if name in DIVINE_DISPLAY and divine_pair.get("rate"):
            entry["divine_rate"] = divine_pair["rate"]
            entry["divine_history"] = divine_pair.get("history", [])
        elif chaos_pair.get("rate"):
            entry["chaos"] = chaos_pair["rate"]
            entry["chaos_history"] = chaos_pair.get("history", [])
        elif divine_pair.get("rate"):
            entry["divine_rate"] = divine_pair["rate"]
            entry["divine_history"] = divine_pair.get("history", [])

        results[name] = entry
    return results

def get_unique_prices():
    data = fetch_json(f"{BASE_URL}/itemoverview?league={LEAGUE}&type=UniqueAccessory")
    results = {}
    item_ids = {}
    for line in data.get("lines", []):
        name = line.get("name", "")
        if name in UNIQUE_ITEMS and name not in results:
            results[name] = {"chaos": line.get("chaosValue", 0), "divine": line.get("divineValue", 0), "url": UNIQUE_ITEMS[name]}
            item_ids[name] = line.get("id")

    for name, item_id in item_ids.items():
        if item_id:
            hist = fetch_json(f"{BASE_URL}/itemhistory?league={LEAGUE}&type=UniqueAccessory&itemId={item_id}")
            results[name]["history"] = hist if isinstance(hist, list) else []
        else:
            results[name]["history"] = []
    return results

def calc_7d_change(history, rate_key="rate"):
    """Calculate 7d change: compare current rate to the point closest to (but not after) 7 days ago."""
    if len(history) < 2:
        return None
    sorted_pts = sorted(history, key=lambda p: p["timestamp"])
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    current = sorted_pts[-1].get(rate_key, 0)

    # Find the latest point that's on or before the 7d cutoff
    seven_ago = None
    for p in sorted_pts:
        ts = datetime.fromisoformat(p["timestamp"].replace("Z", "+00:00"))
        if ts <= cutoff:
            seven_ago = p.get(rate_key, 0)
        else:
            break

    # If no point before cutoff, use the earliest point
    if seven_ago is None:
        seven_ago = sorted_pts[0].get(rate_key, 0)

    if not seven_ago:
        return None
    return round((current - seven_ago) / seven_ago * 100, 1)

def calc_7d_change_item(history):
    if len(history) < 2:
        return None
    sorted_pts = sorted(history, key=lambda p: -p["daysAgo"])
    latest = sorted_pts[-1]
    # Find point closest to 7 days ago
    seven_ago = next((p for p in sorted_pts if p["daysAgo"] >= 7), sorted_pts[0])
    if seven_ago["value"] == 0:
        return None
    return round((latest["value"] - seven_ago["value"]) / seven_ago["value"] * 100, 1)

def exchange_history_to_chart_data(points):
    sorted_pts = sorted(points, key=lambda p: p["timestamp"])[-10:]
    labels = [datetime.fromisoformat(p["timestamp"].replace("Z", "+00:00")).strftime("%-d %b") for p in sorted_pts]
    values = [round(p.get("rate", 0), 1) for p in sorted_pts]
    return labels, values

def build_chart_url(datasets_info, labels):
    colors = ["#E8A524", "#FF5555", "#55FF55", "#55AAFF", "#FF55FF"]
    datasets = []
    for (label, data), color in zip(datasets_info, colors):
        if data:
            datasets.append({"label": label, "data": data, "borderColor": color, "fill": False, "pointRadius": 2, "borderWidth": 2})
    if not datasets:
        return None
    chart = {
        "type": "line",
        "data": {"labels": labels, "datasets": datasets},
        "options": {
            "legend": {"labels": {"fontColor": "#ccc"}},
            "scales": {
                "xAxes": [{"ticks": {"fontColor": "#aaa"}, "gridLines": {"color": "rgba(255,255,255,0.05)"}}],
                "yAxes": [{"ticks": {"fontColor": "#ccc"}, "gridLines": {"color": "rgba(255,255,255,0.1)"}}],
            },
        },
    }
    return f"https://quickchart.io/chart?bkg=%232f3136&w=500&h=250&c={quote(json.dumps(chart))}"

def fmt_change(pct):
    if pct is None:
        return "No Sparkline"
    arrow = "📈" if pct >= 0 else "📉"
    return f"{arrow} {pct:+.1f}%"

def build_embeds(currencies, uniques):
    now = datetime.now(timezone.utc)
    fields = []

    for name, data in currencies.items():
        link = f"[{name}]({data['url']})"
        if "chaos" in data:
            fields.append({"name": f"💠 {link}", "value": f"**{data['chaos']:,.1f}** chaos", "inline": True})
        elif "divine_rate" in data:
            fields.append({"name": f"💠 {link}", "value": f"**{data['divine_rate']:,.1f}** divine", "inline": True})

    for name, prices in uniques.items():
        if prices:
            link = f"[{name}]({prices['url']})"
            fields.append({
                "name": f"🏆 {link}",
                "value": f"**{prices['divine']:,.1f}** divine",
                "inline": True,
            })

    # 7d changes removed — chart speaks for itself

    divine = currencies.get("Divine Orb")
    embed = {
        "title": f"📊 {LEAGUE} League — Price Tracker",
        "color": 0xE8A524,
        "fields": fields,
        "description": "[Contribute on GitHub](https://github.com/antzangell/discord-webhooks)",
        "footer": {"text": "Data from poe.ninja"},
        "timestamp": now.isoformat(),
    }

    if divine and divine.get("chaos_history"):
        labels, values = exchange_history_to_chart_data(divine["chaos_history"])
        chart_url = build_chart_url([("Divine Orb (chaos)", values)], labels)
        if chart_url:
            embed["image"] = {"url": chart_url}

    return {"embeds": [embed]}

DIVINE_ALERT_THRESHOLD = 350

def send_webhook(payload):
    resp = requests.post(WEBHOOK_URL, json=payload)
    if resp.status_code not in (200, 204):
        print(f"Webhook failed: {resp.status_code} {resp.text}", file=sys.stderr)
        sys.exit(1)

def send_alert(price):
    payload = {"content": f"@everyone 🚨 Divine Orbs are at **{price:,.1f}** chaos — dump em!"}
    resp = requests.post(WEBHOOK_URL, json=payload)
    if resp.status_code not in (200, 204):
        print(f"Alert webhook failed: {resp.status_code} {resp.text}", file=sys.stderr)

def main():
    local = "--local" in sys.argv

    if not local and not WEBHOOK_URL:
        print("Error: DISCORD_WEBHOOK_URL env var not set", file=sys.stderr)
        sys.exit(1)

    currencies = get_currency_data()
    uniques = get_unique_prices()

    if local:
        print("=== Prices ===")
        for name, data in currencies.items():
            print(f"  {name}: {data.get('chaos', data.get('divine_rate', '?'))}")
        for name, data in uniques.items():
            print(f"  {name}: {data['chaos']}c / {data['divine']}div")
        return

    payload = build_embeds(currencies, uniques)
    send_webhook(payload)

    divine_price = currencies.get("Divine Orb", {}).get("chaos", 0)
    if divine_price >= DIVINE_ALERT_THRESHOLD:
        send_alert(divine_price)
        print(f"⚠️ Alert sent — Divine at {divine_price}c!")

    print("Posted to Discord.")

if __name__ == "__main__":
    main()
