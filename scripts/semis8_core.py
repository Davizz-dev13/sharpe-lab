"""Estrategia "Rotacion Semis8" (nombre canonico: ensemble top1 multiescala).

Universo: NVDA, AVGO, AMD, TSM, ASML, MU, ON, INTC.
Cada dia, para cada nombre: ROC a 63, 126, 189 y 252 dias; cada horizonte se
estandariza cross-sectionalmente (z-score entre los 8) y se promedian los 4.
Se compra el nombre con mejor score SOLO si es positivo, con tamano
min(1, 0.25/vol20); si ninguno es positivo, 100% cash. Revision diaria,
coste 0.1% por cambio, cash remunerado segun config.
Senal al cierre, posicion desde la barra siguiente (convencion del proyecto).
"""
from __future__ import annotations
import numpy as np
import pandas as pd

SEMIS8 = ["NVDA", "AVGO", "AMD", "TSM", "ASML", "MU", "ON", "INTC"]
HORIZONS = (63, 126, 189, 252)
VOL_DAYS = 20
TARGET_VOL = 0.25


def ensemble_score(closes: pd.DataFrame) -> pd.DataFrame:
    """Score medio de los z-scores cross-sectionales de los 4 horizontes ROC."""
    zs = []
    for h in HORIZONS:
        roc = closes.pct_change(h)
        mu = roc.mean(axis=1)
        sd = roc.std(axis=1, ddof=1)
        zs.append(roc.sub(mu, axis=0).div(sd.replace(0, np.nan), axis=0))
    return sum(zs) / len(zs)


def target_weights(closes: pd.DataFrame) -> pd.DataFrame:
    """Pesos objetivo diarios (senal al cierre de ese dia)."""
    score = ensemble_score(closes)
    vol = closes.pct_change().rolling(VOL_DAYS).std(ddof=1) * np.sqrt(252)
    W = pd.DataFrame(0.0, index=closes.index, columns=closes.columns)
    for i in range(len(closes)):
        s = score.iloc[i].dropna()
        if s.empty:
            continue
        best = s.idxmax()
        if s[best] <= 0:
            continue
        v = vol[best].iloc[i]
        scale = min(1.0, TARGET_VOL / v) if v and v > 1e-9 else 0.0
        W.iloc[i, W.columns.get_loc(best)] = scale
    return W


def backtest(closes: pd.DataFrame, W: pd.DataFrame, cost: float, cash_rate: float) -> pd.Series:
    held = W.shift(1).fillna(0.0)
    asset_ret = closes.pct_change().fillna(0.0)
    invested = held.sum(axis=1).clip(upper=1.0)
    turnover = held.diff().abs().fillna(held.abs()).sum(axis=1)
    cash_daily = cash_rate / 252
    return (asset_ret * held).sum(axis=1) + cash_daily * (1 - invested) - turnover * cost


def rotation_log(W: pd.DataFrame) -> list[dict]:
    """Cambios en el conjunto de patas mantenidas."""
    out, prev = [], None
    for d, row in W.iterrows():
        sel = frozenset(t for t, w in row.items() if w > 0)
        if sel != prev:
            out.append({"date": str(d.date()),
                        "legs": sorted(sel),
                        "weights": {t: round(float(row[t]), 4) for t in sorted(sel)}})
            prev = sel
    return out
