"""Benchmark fijo (SPY) para comparar todas las estrategias con la misma vara."""
from __future__ import annotations

import pandas as pd
import yfinance as yf

BENCHMARK = "SPY"


def benchmark_equity(index: pd.DatetimeIndex, ticker: str = BENCHMARK) -> list[float] | None:
    """Curva de buy & hold de `ticker` alineada a `index` (arrastra el último cierre
    en días sin mercado) y normalizada a 1 en la primera fecha. None si falla."""
    try:
        df = yf.download(ticker, period="max", interval="1d", auto_adjust=True, progress=False, threads=False)
        if df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.index = pd.to_datetime(df.index)
        close = df["Close"].reindex(df.index.union(index)).ffill().reindex(index).bfill()
        eq = close / close.iloc[0]
        return [round(float(v), 4) for v in eq]
    except Exception:  # noqa: BLE001 - el benchmark es opcional, nunca tumba el generador
        return None
