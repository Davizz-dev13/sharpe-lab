#!/usr/bin/env python3
"""Pruebas de sensibilidad para la pagina de metodologia (sesgos conocidos).

Salida: docs/metodologia/sensibilidad.json. Usa exactamente el mismo motor que los
generadores de cada estrategia (semis8_core, semis_core, mag7w_core), la misma
ventana de 10 anos, costes y cash de config/settings.yaml, y el Sharpe de core/stats.py.

1. Semis8 y Semis "sin NVDA": las listas de valores son las de hoy aplicadas a 10
   anos (sesgo de supervivencia/seleccion). Quitar al mejor valor del periodo
   muestra cuanto depende el resultado de haberlo elegido a posteriori.
2. Mag7 con otros niveles de RSI: los niveles 85/87/75/79 se fijaron mirando todo
   el historico; se compara con RSI 70 (la regla original) y 85 para todos.
"""
from __future__ import annotations
import json
from pathlib import Path

import pandas as pd
import yfinance as yf
import yaml

import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.stats import sharpe_ratio
import scripts.semis8_core as s8
import scripts.semis_core as s5
from scripts.mag7w_core import weekly_frame, weekly_position, weekly_backtest

CFG = yaml.safe_load(open(ROOT / "config/settings.yaml", encoding="utf8"))
COST = float(CFG.get("backtest", {}).get("transaction_cost", 0.001))
CASH = float(CFG.get("backtest", {}).get("cash_rate_annual", 0.02))
MAG7W_CFG = CFG.get("mag7w", {})
RSI_DEFAULT = float(MAG7W_CFG.get("rsi_level", 70))
RSI_BY_ASSET = {k: float(v) for k, v in MAG7W_CFG.get("rsi_level_by_asset", {}).items()}
MAG7 = ["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA", "GLD", "BTC-USD", "SPY", "QQQ"]
WINDOW_YEARS = 10

_cache: dict[str, pd.DataFrame] = {}


def download(t: str) -> pd.DataFrame:
    if t not in _cache:
        df = yf.download(t, period="max", interval="1d", auto_adjust=True, progress=False, threads=False)
        if df.empty:
            raise ValueError(f"sin datos para {t}")
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [c.title() for c in df.columns]
        df.index = pd.to_datetime(df.index)
        _cache[t] = df
    return _cache[t]


def summary(ret: pd.Series) -> dict:
    ret = ret.fillna(0.0)
    eq = (1 + ret).cumprod()
    dd = eq / eq.cummax() - 1
    sh = sharpe_ratio(ret, CASH)
    return {"total_return": round((float(eq.iloc[-1]) - 1) * 100, 1),
            "sharpe": round(sh, 2) if sh is not None else None,
            "max_dd": round(float(dd.min()) * 100, 1)}


def window(s: pd.Series) -> pd.Series:
    return s[s.index >= s.index[-1] - pd.DateOffset(years=WINDOW_YEARS)]


def rotation(mod, universe: list[str]) -> dict:
    C = pd.DataFrame({t: download(t)["Close"] for t in universe}).dropna()
    W = mod.target_weights(C)
    r = window(mod.backtest(C, W, COST, CASH))
    bh = window(C.pct_change().fillna(0.0).mean(axis=1))
    return {"universe": universe, "strategy": summary(r), "buy_hold": summary(bh)}


def mag7(level_of) -> dict:
    rets = []
    for t in MAG7:
        x = weekly_frame(download(t))
        pos = weekly_position(x, level_of(t))
        rets.append(weekly_backtest(x, pos, COST, CASH).rename(t))
    p = pd.concat(rets, axis=1).mean(axis=1).dropna()
    return summary(window(p))


def main():
    out = {"generated_at": pd.Timestamp.now('UTC').isoformat(), "window_years": WINDOW_YEARS,
           "cash_rate": CASH, "cost": COST, "errors": []}
    try:
        out["semis8"] = {"publicada": rotation(s8, list(s8.SEMIS8)),
                         "sin_nvda": rotation(s8, [t for t in s8.SEMIS8 if t != "NVDA"])}
        out["semis"] = {"publicada": rotation(s5, list(s5.SEMIS)),
                        "sin_nvda": rotation(s5, [t for t in s5.SEMIS if t != "NVDA"])}
    except Exception as e:  # noqa: BLE001
        out["errors"].append(f"semis: {e}")
    try:
        out["mag7"] = {"config": mag7(lambda t: RSI_BY_ASSET.get(t, RSI_DEFAULT)),
                       "rsi70": mag7(lambda t: 70.0),
                       "rsi85": mag7(lambda t: 85.0)}
    except Exception as e:  # noqa: BLE001
        out["errors"].append(f"mag7: {e}")
    p = ROOT / "docs" / "metodologia" / "sensibilidad.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False))
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
