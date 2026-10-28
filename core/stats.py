"""Métricas comunes de rendimiento (Sharpe, anualización) para todos los generadores.

- El Sharpe se calcula sobre el EXCESO de rentabilidad: a cada barra se le resta la
  tasa libre de riesgo (la misma remuneración del cash que usan los backtests,
  `cash_rate_annual` en config/settings.yaml) repartida entre las barras del año.
- La anualización usa las barras por año REALES de la serie (≈252 en bolsa, ≈365
  en BTC o en un calendario unión con fines de semana), medidas con las fechas,
  en vez de un √252 fijo.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def years_between(index) -> float:
    """Años naturales cubiertos por un índice de fechas."""
    if len(index) < 2:
        return 0.0
    return (pd.Timestamp(index[-1]) - pd.Timestamp(index[0])).days / 365.25


def periods_per_year(index) -> float:
    """Barras por año reales del índice (252 si no se puede medir)."""
    yrs = years_between(index)
    if yrs <= 0:
        return 252.0
    return (len(index) - 1) / yrs


def sharpe_ratio(ret: pd.Series, rf_annual: float = 0.0, ppy: float | None = None) -> float | None:
    """Sharpe anualizado sobre el exceso de rentabilidad respecto a `rf_annual`."""
    ret = ret.fillna(0.0)
    if len(ret) < 2:
        return None
    ppy = ppy or periods_per_year(ret.index)
    excess = ret - rf_annual / ppy
    sd = excess.std(ddof=1)
    if not sd or sd <= 1e-12 or not np.isfinite(sd):
        return None
    return float(excess.mean() / sd * np.sqrt(ppy))
