#!/usr/bin/env python3
"""Regenerate docs/optimizador/optimizador.json: 5y daily returns for the
portfolio-optimizer universe (cash, gold, commodities, S&P 500, Bitcoin).
Runs nightly via GitHub Actions alongside the dashboard."""
from __future__ import annotations
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.data import history

ASSETS = [
    {"ticker": "BIL",     "name": "Cash remunerado", "short": "Cash"},
    {"ticker": "GLD",     "name": "Oro",             "short": "Oro"},
    {"ticker": "PDBC",    "name": "Commodities",     "short": "Commodities"},
    {"ticker": "SPY",     "name": "S&P 500",         "short": "S&P 500"},
    {"ticker": "BTC-USD", "name": "Bitcoin",         "short": "Bitcoin"},
    {"ticker": "URTH",    "name": "MSCI World",      "short": "MSCI World"},
    {"ticker": "EEM",     "name": "Emergentes",      "short": "Emergentes"},
    {"ticker": "SLV",     "name": "Plata",           "short": "Plata"},
]
PERIOD = "5y"


def main():
    closes = {}
    for a in ASSETS:
        df = history(a["ticker"], PERIOD, "1d", refresh=True)
        closes[a["ticker"]] = df["Close"]

    # Calendario union (BTC cotiza 365, los ETFs solo dias laborables):
    # reindexar todo al calendario de BTC y rellenar huecos con el ultimo cierre.
    cal = closes["BTC-USD"].index
    px = pd.DataFrame({t: s.reindex(cal).ffill() for t, s in closes.items()}).dropna()
    rets = px.pct_change().dropna()

    dates = [d.strftime("%Y-%m-%d") for d in rets.index]
    out = {
        "generated_at": pd.Timestamp.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "period": PERIOD,
        "assets": ASSETS,
        "dates": dates,
        "returns": {t: [round(float(x), 6) for x in rets[t].values] for t in rets.columns},
        "last_prices": {t: round(float(px[t].iloc[-1]), 2) for t in px.columns},
    }
    dest = ROOT / "docs" / "optimizador"
    dest.mkdir(parents=True, exist_ok=True)
    with open(dest / "optimizador.json", "w") as f:
        json.dump(out, f, separators=(",", ":"))
    print(f"optimizador.json: {len(dates)} dias x {len(ASSETS)} activos, {dest/'optimizador.json'}")


if __name__ == "__main__":
    main()
