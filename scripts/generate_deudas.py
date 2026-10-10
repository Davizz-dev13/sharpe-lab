"""Deuda diaria de BTC (fechada el día que abre, NY): rango de la vela de 5 min 23:55-00:00 (America/New_York), BTC-USD spot Coinbase.
Escribe docs/deudas/deudas.json. Los niveles semanal/mensual/acumulacion viven en docs/deudas/niveles.json."""
import json, time, urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
API = "https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=300&start=%s&end=%s"
DAYS = 40

def get(start, end):
    f = "%Y-%m-%dT%H:%M:%SZ"
    for _ in range(4):
        try:
            req = urllib.request.Request(API % (start.strftime(f), end.strftime(f)), headers={"User-Agent": "sharpe-lab"})
            return json.loads(urllib.request.urlopen(req, timeout=30).read())
        except Exception:
            time.sleep(2)
    raise SystemExit("coinbase no responde")

def candles(start, end):
    out, cur = {}, start
    while cur < end:
        nxt = min(cur + timedelta(hours=24), end)
        for t, lo, hi, op, cl, v in get(cur, nxt):
            out[t] = (lo, hi, op, cl)
        cur = nxt
    return out

now = datetime.now(timezone.utc)
today_ny = now.astimezone(NY).date()
first = today_ny - timedelta(days=DAYS)
data = candles(datetime.combine(first, datetime.min.time(), NY).astimezone(timezone.utc) - timedelta(hours=1), now)
ts = sorted(data)
rows = []
for i in range(DAYS):
    d = first + timedelta(days=i)
    start = datetime.combine(d, datetime.min.time(), NY).replace(hour=23, minute=55)
    t0 = int(start.astimezone(timezone.utc).timestamp())
    if t0 not in data or t0 + 300 > ts[-1]:
        continue
    lo, hi = data[t0][0], data[t0][1]
    side, paid, paid_at = None, False, None
    for t in ts:
        if t <= t0:
            continue
        l, h, o, c = data[t]
        if side is None:
            if c > hi: side = "up"
            elif c < lo: side = "down"
            continue
        if (side == "up" and l <= lo) or (side == "down" and h >= hi):
            paid, paid_at = True, datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
            break
    rows.append({"date": (d + timedelta(days=1)).isoformat(), "low": lo, "high": hi, "paid": paid, "paid_at": paid_at, "side": side})
rows.reverse()
json.dump({"updated": now.strftime("%Y-%m-%dT%H:%MZ"), "rows": rows}, open("docs/deudas/deudas.json", "w"), indent=1)
print(len(rows), rows[:3])
