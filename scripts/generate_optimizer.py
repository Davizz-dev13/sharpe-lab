#!/usr/bin/env python3
"""Regenerate docs/optimizador/optimizador.json: 5y daily returns for the
portfolio-optimizer universe. Runs nightly via GitHub Actions."""
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
    {"ticker": "BIL",     "name": "Cash (T-bill ETF)",  "short": "Cash"},
    {"ticker": "GLD",     "name": "Gold",               "short": "Gold"},
    {"ticker": "PDBC",    "name": "Commodities",        "short": "Commodities"},
    {"ticker": "SPY",     "name": "S&P 500",            "short": "S&P 500"},
    {"ticker": "BTC-USD", "name": "Bitcoin",            "short": "Bitcoin"},
    {"ticker": "URTH",    "name": "MSCI World",         "short": "MSCI World"},
    {"ticker": "EEM",     "name": "Emerging Markets",   "short": "Emerging"},
    {"ticker": "SLV",     "name": "Silver",             "short": "Silver"},
    {"ticker": "HG=F",    "name": "Copper",             "short": "Copper"},
    {"ticker": "ETH-USD", "name": "Ethereum",           "short": "Ethereum"},
    {"ticker": "SOL-USD", "name": "Solana",             "short": "Solana"},
    {"ticker": "QQQ",     "name": "Nasdaq 100",         "short": "Nasdaq 100"},
    {"ticker": "TLT",     "name": "US Bonds 20+Y",      "short": "Bonds 20Y"},
    {"ticker": "MCHI",    "name": "MSCI China",         "short": "MSCI China"},
    {"ticker": "EWJ",     "name": "MSCI Japan",         "short": "MSCI Japan"},
    {"ticker": "INDA",    "name": "MSCI India",         "short": "MSCI India"},
    {"ticker": "VGK",     "name": "FTSE Europe",        "short": "FTSE Europe"},
    {"ticker": "CL=F",    "name": "Oil WTI",            "short": "Oil WTI"},
    {"ticker": "NVDA",    "name": "NVIDIA",             "short": "NVIDIA"},
    {"ticker": "AAPL",    "name": "Apple",              "short": "Apple"},
    {"ticker": "MSFT",    "name": "Microsoft",          "short": "Microsoft"},
    {"ticker": "GOOGL",   "name": "Alphabet",           "short": "Alphabet"},
    {"ticker": "AMZN",    "name": "Amazon",             "short": "Amazon"},
    {"ticker": "META",    "name": "Meta",               "short": "Meta"},
    {"ticker": "TSLA",    "name": "Tesla",              "short": "Tesla"},
    {"ticker": "AVGO",    "name": "Broadcom",           "short": "Broadcom"},
    {"ticker": "ASTS",    "name": "AST SpaceMobile",    "short": "ASTS"},
]
PERIOD = "5y"
LONG_PERIOD = "20y"
# Long-window overrides: same asset, different source where the 5y one lacks history.
LONG_TICKER = {"PDBC": "DBC"}  # Commodities: DBC covers the full 20y window
LONG_NAME = {"PDBC": "Commodities (DBC)"}


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


def main_long():
    """optimizador-long.json: 20y daily returns. Assets without full history
    keep leading nulls (no invented backfill); the page excludes them per window."""
    closes = {}
    assets = []
    for a in ASSETS:
        o = dict(a)
        if a["ticker"] in LONG_TICKER:
            o["ticker"] = LONG_TICKER[a["ticker"]]
            o["name"] = LONG_NAME[a["ticker"]]
        assets.append(o)
        df = history(o["ticker"], LONG_PERIOD, "1d", refresh=True)
        closes[o["ticker"]] = df["Close"]

    cal = pd.Index(sorted(set().union(*[s.index for s in closes.values()])))
    px = pd.DataFrame({t: s.reindex(cal).ffill() for t, s in closes.items()})

    rets = px.pct_change(fill_method=None)

    # Cash splice: before BIL inception (2007-05), accrue the 3M T-bill yield (^IRX).
    irx = history("^IRX", LONG_PERIOD, "1d", refresh=True)["Close"].reindex(cal).ffill()
    bil_start = px["BIL"].first_valid_index()
    cash_ret = rets["BIL"].copy()
    pre = cal <= bil_start
    cash_ret[pre] = irx[pre] / 100.0 / 365.0
    rets["BIL"] = cash_ret

    rets = rets.iloc[1:]
    dates = [d.strftime("%Y-%m-%d") for d in rets.index]
    starts = {}
    for t in rets.columns:
        fv = rets[t].first_valid_index()
        starts[t] = fv.strftime("%Y-%m-%d") if fv is not None else None
    out = {
        "generated_at": pd.Timestamp.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "period": LONG_PERIOD,
        "assets": assets,
        "dates": dates,
        "returns": {t: [None if pd.isna(x) else round(float(x), 6) for x in rets[t].values] for t in rets.columns},
        "starts": starts,
        "notes": {
            "BIL": "Cash: BIL (T-bill ETF); before 2007-05 it accrues the 3-month T-bill yield (^IRX).",
            "DBC": "Commodities: DBC broad basket (the 5y window uses PDBC).",
        },
    }
    dest = ROOT / "docs" / "optimizador"
    with open(dest / "optimizador-long.json", "w") as f:
        json.dump(out, f, separators=(",", ":"))
    print(f"optimizador-long.json: {len(dates)} dias x {len(assets)} activos")


def run_all():
    main()
    main_long()


if __name__ == "__main__":
    run_all()
