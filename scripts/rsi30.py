#!/usr/bin/env python3
"""Estrategia RSI30: compra cuando el RSI(14) cierra <= 30 y compara varias salidas.

Pensado para vivir en scripts/rsi30.py de sharpe-lab (lee config/settings.yaml si
lo encuentra: transaction_cost y cash_rate_annual, igual que generate_semis8.py).

Reglas comunes
- Senal al CIERRE de la vela t (RSI14 Wilder, mismo calculo que core/metrics.py).
- Ejecucion a la APERTURA de la vela t+1 (sin look-ahead).
- Coste por lado = transaction_cost (0,1 %), aplicado a cada compra y venta.
- El cash parado cobra cash_rate_annual (2 %) repartido por vela.
- Sharpe = media(exceso sobre el cash) / sd * sqrt(velas/ano).
- Sin piramidacion por defecto: con posicion abierta se ignoran nuevas senales.
  Variante scale-in: tercios; se anade 1/3 en cada cierre con RSI<=30 por debajo
  del precio de la ultima compra (promediar a la baja), maximo 3 tercios.
- Take profit y stop-loss son ordenes en el mercado: se llenan dentro de la vela
  (al nivel, o a la apertura si la vela abre ya mas alla). Si en la misma vela se
  tocan los dos, se supone que salta antes el stop (conservador).
- El resto de salidas (RSI, EMA20, MACD, trailing, tiempo) se miran al cierre y se
  ejecutan en la apertura siguiente.
- Tras un stop-loss no se recompra hasta que el RSI vuelva por encima de 30 y
  luego cierre de nuevo <= 30 (evita recomprar al dia siguiente en bucle).

Walk-forward: cada serie se parte por la mitad (fechas). Los parametros se eligen
SOLO con la primera mitad (in-sample) y la segunda (out-of-sample) se informa
aparte. Cada mitad empieza sin posicion; los indicadores son causales.

Uso: python scripts/rsi30.py [--out DIR] [--refresh]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

HERE = Path(__file__).resolve().parent
CANDIDATE_ROOTS = [HERE.parent, Path.cwd()]
ROOT = next((p for p in CANDIDATE_ROOTS if (p / "config/settings.yaml").exists()), None)
CFG = yaml.safe_load(open(ROOT / "config/settings.yaml", encoding="utf8")) if ROOT else {}
COST = float(CFG.get("backtest", {}).get("transaction_cost", 0.001))
CASH = float(CFG.get("backtest", {}).get("cash_rate_annual", 0.02))

PRIMARY = ["BTC-USD", "SPY", "GC=F"]   # David (28/10, 19:59): XAU, BTC y SPY
# XAU: no hay XAUUSD spot gratis en Yahoo (XAUUSD=X no existe) y Stooq ya no sirve
# CSV sin clave; se usa el futuro continuo del oro GC=F (desde 2000) y GLD como
# comprobacion (ETF real, desde 2004, cobra 0,40 %/ano).
EXTRA = ["GLD"]
CRYPTO = {"BTC-USD", "ETH-USD"}

RSI_ENTRY = 30.0


def _clean_json(o):
    """NaN/inf de float -> None: la web solo lee JSON estricto (json.dumps escribe NaN)."""
    if isinstance(o, dict):
        return {k: _clean_json(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean_json(v) for v in o]
    if isinstance(o, float) and not math.isfinite(o):
        return None
    if isinstance(o, np.generic):
        return _clean_json(o.item())
    return o


# ---------------------------------------------------------------- datos
def download(t: str, cache: Path, refresh: bool = False) -> pd.DataFrame:
    cache.mkdir(parents=True, exist_ok=True)
    p = cache / (t.replace("^", "IDX_").replace("=", "_") + "_max_1d.csv")
    if p.exists() and not refresh:
        df = pd.read_csv(p, index_col=0, parse_dates=True)
    else:
        import yfinance as yf
        df = yf.download(t, period="max", interval="1d", auto_adjust=True, progress=False, threads=False)
        if df.empty:
            raise ValueError(f"sin datos para {t}")
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [c.title() for c in df.columns]
        df.index = pd.to_datetime(df.index).tz_localize(None)
        df = df[["Open", "High", "Low", "Close"]]
        df.to_csv(p)
    df = df.dropna()
    df = df[(df[["Open", "High", "Low", "Close"]] > 0).all(axis=1)].copy()
    # GC=F trae ~5 % de velas con High/Low incoherentes (High < Open/Close): se acotan.
    df["High"] = df[["High", "Open", "Close"]].max(axis=1)
    df["Low"] = df[["Low", "Open", "Close"]].min(axis=1)
    return df


def to_weekly(df: pd.DataFrame, crypto: bool) -> pd.DataFrame:
    rule = "W-SUN" if crypto else "W-FRI"   # vela semanal de TradingView: lun-dom en cripto
    w = df.resample(rule).agg({"Open": "first", "High": "max", "Low": "min", "Close": "last"}).dropna()
    # La ultima semana puede estar a medias: se descarta si no ha cerrado.
    if w.index[-1] > df.index[-1]:
        w = w.iloc[:-1]
    return w


def indicators(df: pd.DataFrame) -> pd.DataFrame:
    x = df.copy()
    c = x["Close"]
    # RSI(14) Wilder, identico a core/metrics.py:signal_frame
    delta = c.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    ag = gain.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    al = loss.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    rs = ag / al.replace(0, np.nan)
    x["RSI14"] = 100 - 100 / (1 + rs)
    x["EMA20"] = c.ewm(span=20, adjust=False).mean()
    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    x["MACD"] = ema12 - ema26
    x["MACDsig"] = x["MACD"].ewm(span=9, adjust=False).mean()
    return x


def bars_per_year(idx: pd.DatetimeIndex) -> float:
    yrs = (idx[-1] - idx[0]).days / 365.25
    return len(idx) / yrs


# ---------------------------------------------------------------- reglas
def rule_grid(tf: str) -> list[dict]:
    time_n = [20, 60, 120] if tf == "1d" else [4, 13, 26]
    base = []
    for X in (50, 60, 70):
        base.append({"family": "a", "name": f"RSI>{X}", "X": X})
    for Y in (10, 20, 40):
        base.append({"family": "b", "name": f"TP+{Y}%", "Y": Y / 100})
    for X in (60, 70):
        base.append({"family": "c", "name": f"RSI>{X} y cierre<EMA20", "X": X, "conf": "ema20"})
        base.append({"family": "c", "name": f"RSI>{X} y MACD bajista", "X": X, "conf": "macd"})
    for X in (50, 70):
        base.append({"family": "c", "name": f"RSI>{X} y ganancia>=10%", "X": X, "conf": "gain", "Y": 0.10})
    for X in (60, 70):
        for T in (10, 20):
            base.append({"family": "d", "name": f"RSI>{X} y trailing {T}%", "X": X, "T": T / 100})
    for n in time_n:
        base.append({"family": "e", "name": f"Tiempo {n} velas", "N": n})
    out = []
    for r in base:
        for sl in (None, 0.15):
            rr = dict(r)
            rr["SL"] = sl
            rr["rule"] = r["name"] + (f" + SL-{int(sl*100)}%" if sl else "")
            out.append(rr)
    return out


# ---------------------------------------------------------------- motor
def simulate(x: pd.DataFrame, rule: dict, i0: int, i1: int, cost: float, cash_bar,
             scale_in: bool = False) -> dict:
    """Simula de la vela i0 a la i1 (incluidas). cash_bar: float o array por vela."""
    O = x["Open"].to_numpy(); H = x["High"].to_numpy(); L = x["Low"].to_numpy()
    C = x["Close"].to_numpy(); R = x["RSI14"].to_numpy(); E = x["EMA20"].to_numpy()
    M = x["MACD"].to_numpy(); S = x["MACDsig"].to_numpy()
    cb = np.broadcast_to(np.asarray(cash_bar, dtype=float), (len(C),)) if np.ndim(cash_bar) else np.full(len(C), float(cash_bar))
    idx = x.index
    fam = rule["family"]; X = rule.get("X"); Y = rule.get("Y"); T = rule.get("T")
    N = rule.get("N"); SL = rule.get("SL"); conf = rule.get("conf")

    cash, sh = 1.0, 0.0
    units = 0; last_fill = None; cost_basis = 0.0; qty_bought = 0.0
    entry_i = None; armed = False; peak = None
    need_reset = False
    pend_buy = 0.0; pend_sell = False
    eq = np.empty(i1 - i0 + 1); inmkt = np.zeros(i1 - i0 + 1, dtype=bool)
    trades = []; marks = []

    def close_trade(i, px, why):
        nonlocal cash, sh, units, last_fill, cost_basis, qty_bought, entry_i, armed, peak
        proceeds = sh * px * (1 - cost)
        cash += proceeds
        trades.append({"entry_date": str(idx[entry_i].date()), "exit_date": str(idx[i].date()),
                       "entry_px": cost_basis / qty_bought, "exit_px": px, "units": units,
                       "bars": i - entry_i, "ret": proceeds / cost_basis - 1, "exit": why})
        marks.append((idx[i], px, "sell"))
        sh = 0.0; units = 0; last_fill = None; cost_basis = 0.0; qty_bought = 0.0
        entry_i = None; armed = False; peak = None

    for k, i in enumerate(range(i0, i1 + 1)):
        if k > 0:
            cash *= 1 + cb[i]
        # --- apertura: ordenes pendientes de la vela anterior
        if pend_sell and sh > 0:
            close_trade(i, O[i], pend_sell)
        pend_sell = False
        if pend_buy > 0:
            equity_o = cash + sh * O[i]
            spend = min(cash, pend_buy * equity_o)
            if spend > 1e-12:
                q = spend * (1 - cost) / O[i]
                sh += q; cash -= spend; cost_basis += spend; qty_bought += q
                units += 1; last_fill = O[i]
                if entry_i is None:
                    entry_i = i
                marks.append((idx[i], O[i], "buy"))
        pend_buy = 0.0
        # --- dentro de la vela: stop-loss y take profit (ordenes en mercado)
        if sh > 0:
            avg = cost_basis / qty_bought
            sl_px = avg * (1 - SL) if SL else None
            tp_px = avg * (1 + Y) if fam == "b" else None
            if sl_px is not None and L[i] <= sl_px:
                close_trade(i, min(O[i], sl_px), "stop")
                need_reset = True
            elif tp_px is not None and H[i] >= tp_px:
                close_trade(i, max(O[i], tp_px), "take profit")
        # --- cierre: senales para la vela siguiente
        r = R[i]
        if need_reset and not np.isnan(r) and r > RSI_ENTRY:
            need_reset = False
        if sh > 0:
            if not armed and X is not None and r > X:
                armed = True
                peak = C[i]
            if armed and peak is not None:
                peak = max(peak, C[i])
            exit_now = None
            if fam == "a" and r > X:
                exit_now = "RSI"
            elif fam == "c" and armed:
                if conf == "ema20" and C[i] < E[i]:
                    exit_now = "EMA20"
                elif conf == "macd" and M[i] < S[i]:
                    exit_now = "MACD"
                elif conf == "gain" and r > X and C[i] >= (cost_basis / qty_bought) * (1 + Y):
                    exit_now = "RSI+ganancia"
            elif fam == "d" and armed and C[i] <= peak * (1 - T):
                exit_now = "trailing"
            elif fam == "e" and i - entry_i + 1 >= N:
                exit_now = "tiempo"
            if exit_now and i < i1:
                pend_sell = exit_now
            elif scale_in and units < 3 and not np.isnan(r) and r <= RSI_ENTRY and C[i] < last_fill and i < i1:
                pend_buy = 1.0 / 3.0
        elif not need_reset and not np.isnan(r) and r <= RSI_ENTRY and i < i1:
            pend_buy = (1.0 / 3.0) if scale_in else 1.0
        eq[k] = cash + sh * C[i]
        inmkt[k] = sh > 0
    open_trade = None
    if sh > 0:
        open_trade = {"entry_date": str(idx[entry_i].date()), "entry_px": cost_basis / qty_bought,
                      "mark_px": C[i1], "units": units, "ret_mtm": sh * C[i1] * (1 - cost) / cost_basis - 1}
    return {"equity": pd.Series(eq, index=idx[i0:i1 + 1]), "inmkt": inmkt, "trades": trades,
            "open_trade": open_trade, "marks": marks}


def bh(x: pd.DataFrame, i0: int, i1: int, cost: float) -> pd.Series:
    C = x["Close"].to_numpy(); O = x["Open"].to_numpy()
    e = (1 - cost) * C[i0:i1 + 1] / O[i0]
    return pd.Series(e, index=x.index[i0:i1 + 1])


def stats(eq: pd.Series, cash_bar, bpy: float, inmkt=None, trades=None, open_trade=None) -> dict:
    """Mismo estilo que _stats de core/backtest.py, pero el Sharpe descuenta el cash."""
    ret = eq.pct_change().fillna(eq.iloc[0] - 1.0)
    rf = pd.Series(np.broadcast_to(np.asarray(cash_bar, dtype=float), (len(ret),)) if np.ndim(cash_bar) else float(cash_bar), index=ret.index)
    ex = ret - rf
    sd = ex.std(ddof=1)
    years = max((eq.index[-1] - eq.index[0]).days / 365.25, 1 / 52)
    dd = eq / eq.cummax() - 1
    out = {
        "CAGR": float(eq.iloc[-1] ** (1 / years) - 1),
        "Sharpe": float(ex.mean() / sd * math.sqrt(bpy)) if sd > 1e-12 else np.nan,
        "MaxDD": float(min(dd.min(), 0.0)),
        "TotalReturn": float(eq.iloc[-1] - 1),
        "Years": round(years, 2),
    }
    if inmkt is not None:
        out["TimeInMarket"] = float(inmkt.mean())
    if trades is not None:
        rets = np.array([t["ret"] for t in trades])
        out["Trades"] = len(trades)
        out["OpenTrade"] = int(open_trade is not None)
        out["WinRate"] = float((rets > 0).mean()) if len(rets) else np.nan
        out["AvgWin"] = float(rets[rets > 0].mean()) if (rets > 0).any() else np.nan
        out["AvgLoss"] = float(rets[rets <= 0].mean()) if (rets <= 0).any() else np.nan
        out["AvgBars"] = float(np.mean([t["bars"] for t in trades])) if trades else np.nan
    return out


# ---------------------------------------------------------------- main
def run(out: Path, refresh: bool, cash_mode: str = "flat", cache: Path | None = None):
    cache = cache or (out / "data_cache")
    series = {}
    errors = []
    irx = None
    if cash_mode == "irx":
        irx = download("^IRX", cache, refresh)["Close"] / 100.0
    for t in PRIMARY + EXTRA:
        try:
            d = download(t, cache, refresh)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{t}: {e}")
            continue
        series[(t, "1d")] = indicators(d)
        series[(t, "1w")] = indicators(to_weekly(d, t in CRYPTO))

    rows, picks, sims = [], {}, {}
    for (t, tf), x in series.items():
        x = x.dropna(subset=["RSI14"])
        bpy = bars_per_year(x.index)
        if irx is not None:
            cb = (irx.reindex(x.index, method="ffill").bfill().to_numpy()) / bpy
        else:
            cb = CASH / bpy
        n = len(x)
        mid = n // 2
        halves = {"IS": (0, mid - 1), "OOS": (mid, n - 1)}
        for half, (i0, i1) in halves.items():
            cbh = cb if np.ndim(cb) == 0 else cb
            b = bh(x, i0, i1, COST)
            bs = stats(b, cbh if np.ndim(cbh) == 0 else cbh[i0:i1 + 1], bpy)
            rows.append({"asset": t, "tf": tf, "half": half, "start": str(x.index[i0].date()),
                         "end": str(x.index[i1].date()), "family": "B&H", "rule": "Buy & hold",
                         "scale_in": False, **bs, "TimeInMarket": 1.0})
            for rule in rule_grid(tf):
                for sc in (False, True):
                    s = simulate(x, rule, i0, i1, COST, cb, scale_in=sc)
                    st = stats(s["equity"], cb if np.ndim(cb) == 0 else cb[i0:i1 + 1], bpy,
                               s["inmkt"], s["trades"], s["open_trade"])
                    rows.append({"asset": t, "tf": tf, "half": half, "start": str(x.index[i0].date()),
                                 "end": str(x.index[i1].date()), "family": rule["family"],
                                 "rule": rule["rule"], "scale_in": sc, **st})
                    sims[(t, tf, half, rule["rule"], sc)] = s
    df = pd.DataFrame(rows)
    return df, series, sims, errors



# ---------------------------------------------------------------- seleccion, graficos y JSON
def select_rules(df: pd.DataFrame, assets=None) -> pd.DataFrame:
    """Ranking SOLO in-sample, criterio fijado antes de mirar el OOS: para cada
    temporalidad, rango medio del Sharpe IS de cada regla en los activos de David
    (BTC, SPY y oro). Las columnas OOS se anaden solo para informar."""
    assets = assets or PRIMARY
    s = df[(df.family != "B&H") & (~df.scale_in) & (df.asset.isin(assets))]
    out = []
    for tf in ("1d", "1w"):
        g = s[s.tf == tf]
        isr = g[g.half == "IS"].pivot(index="rule", columns="asset", values="Sharpe")
        oos = g[g.half == "OOS"].pivot(index="rule", columns="asset", values="Sharpe")
        m = pd.DataFrame({
            "IS_mean_rank": isr.rank(ascending=False).mean(axis=1),
            "IS_mean_sharpe": isr.mean(axis=1), "IS_min_sharpe": isr.min(axis=1),
            "IS_trades": g[g.half == "IS"].groupby("rule").Trades.sum(),
            "OOS_mean_sharpe": oos.mean(axis=1), "OOS_min_sharpe": oos.min(axis=1),
            "OOS_mean_rank": oos.rank(ascending=False).mean(axis=1),
            "OOS_trades": g[g.half == "OOS"].groupby("rule").Trades.sum(),
        })
        m = m.join(isr.add_prefix("IS_sharpe_")).join(oos.add_prefix("OOS_sharpe_"))
        bh_ = df[(df.family == "B&H") & (df.tf == tf) & (df.asset.isin(assets))].groupby("half").Sharpe.mean()
        m["BH_IS_mean_sharpe"] = bh_["IS"]; m["BH_OOS_mean_sharpe"] = bh_["OOS"]
        m["tf"] = tf
        out.append(m.reset_index().sort_values("IS_mean_rank"))
    return pd.concat(out)


def chained(x, rule, cost, cb):
    n = len(x); mid = n // 2
    parts, marks, trades = [], [], []
    bhp = []
    level = 1.0; blevel = 1.0
    for i0, i1 in ((0, mid - 1), (mid, n - 1)):
        s = simulate(x, rule, i0, i1, cost, cb)
        parts.append(s["equity"] * level); level = parts[-1].iloc[-1]
        b = bh(x, i0, i1, cost); bhp.append(b * blevel); blevel = bhp[-1].iloc[-1]
        marks += s["marks"]; trades += s["trades"]
    ot = s["open_trade"]  # posicion abierta al final de la 2.a mitad (= hoy), para el estado actual de la web
    if ot is not None:
        trades.append({"entry_date": ot["entry_date"], "exit_date": None, "entry_px": ot["entry_px"],
                       "exit_px": float(ot["mark_px"]), "units": ot["units"], "ret": ot["ret_mtm"], "exit": "abierta"})
    return pd.concat(parts), pd.concat(bhp), marks, x.index[mid], trades


def simulate_shown(series: dict, rules: list[str]) -> dict:
    """Curvas IS+OOS encadenadas de las reglas que se muestran (para el JSON y los PNG)."""
    res = {}
    for key in [(a, "1d") for a in PRIMARY]:
        x = series[key].dropna(subset=["RSI14"])
        cb = CASH / bars_per_year(x.index)
        res[key] = {}
        for rn in rules:
            rule = next(r for r in rule_grid(key[1]) if r["rule"] == rn)
            res[key][rn] = chained(x, rule, COST, cb)
    return res


def make_charts(series: dict, out: Path, rules: list[str]):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    panels = [(a, "1d") for a in PRIMARY]
    names = {"BTC-USD": "BTC", "SPY": "SPY", "GC=F": "Oro (GC=F)"}
    colors = ["#1f77b4", "#ff7f0e"]
    res = simulate_shown(series, rules)
    # 1) capital vs B&H
    fig, axs = plt.subplots(3, 1, figsize=(11, 11))
    for ax, key in zip(axs, panels):
        for c, rn in zip(colors, rules):
            eq, b, _, split, _ = res[key][rn]
            ax.plot(eq.index, eq.values, color=c, lw=1.3, label=rn)
        ax.plot(b.index, b.values, color="0.45", lw=1.0, label="Buy & hold")
        ax.axvline(split, color="k", ls="--", lw=0.8)
        ax.text(split, b.max(), "  OOS →", va="top", fontsize=8)
        ax.set_yscale("log"); ax.set_title(f"{names[key[0]]} diario: capital (escala log)", fontsize=10)
        ax.grid(alpha=0.25); ax.legend(fontsize=8, loc="upper left")
    fig.suptitle("Entrada RSI(14) ≤ 30 en la apertura siguiente · coste 0,1 %/lado · cash 2 %\nIS (1.ª mitad) y OOS (2.ª mitad) simulados por separado; la regla se eligió solo con el IS", fontsize=10.5)
    fig.tight_layout(); fig.savefig(out / "rsi30_equity_vs_bh.png", dpi=125); plt.close(fig)
    # 2) drawdown
    fig, axs = plt.subplots(3, 1, figsize=(11, 9))
    for ax, key in zip(axs, panels):
        eq, b, _, split, _ = res[key][rules[0]]
        ddb = b / b.cummax() - 1; dds = eq / eq.cummax() - 1
        ax.fill_between(ddb.index, ddb.values * 100, 0, color="0.6", alpha=0.5, label=f"Buy & hold (mín {ddb.min()*100:.0f} %)")
        ax.plot(dds.index, dds.values * 100, color=colors[0], lw=1.1, label=f"{rules[0]} (mín {dds.min()*100:.0f} %)")
        ax.axvline(split, color="k", ls="--", lw=0.8)
        ax.set_title(f"{names[key[0]]} diario: drawdown (%)", fontsize=10); ax.grid(alpha=0.25); ax.legend(fontsize=8, loc="lower left")
    fig.suptitle("Drawdown de la regla recomendada frente a buy & hold (la línea discontinua separa IS y OOS)", fontsize=10.5)
    fig.tight_layout(); fig.savefig(out / "rsi30_drawdown.png", dpi=125); plt.close(fig)
    # 3) entradas y salidas en el tramo OOS (precio + RSI)
    fig, axs = plt.subplots(2, 3, figsize=(16, 7.5), gridspec_kw={"height_ratios": [2.2, 1]}, sharex="col")
    for col, key in enumerate(panels):
        x = series[key].dropna(subset=["RSI14"])
        _, _, marks, split, _ = res[key][rules[0]]
        x = x[x.index >= split]
        ax = axs[0, col]
        ax.plot(x.index, x.Close, color="0.2", lw=0.8)
        bm = [m_ for m_ in marks if m_[2] == "buy" and m_[0] >= split]
        sm = [m_ for m_ in marks if m_[2] == "sell" and m_[0] >= split]
        ax.scatter([m_[0] for m_ in bm], [m_[1] for m_ in bm], marker="^", color="#2ca02c", s=55, zorder=3, label="Compra (RSI ≤ 30)")
        ax.scatter([m_[0] for m_ in sm], [m_[1] for m_ in sm], marker="v", color="#d62728", s=55, zorder=3, label="Venta")
        ax.set_yscale("log"); ax.grid(alpha=0.25)
        ax.set_title(f"{names[key[0]]} diario, tramo OOS: {rules[0]}", fontsize=9.5); ax.legend(fontsize=7.5, loc="upper left")
        ax2 = axs[1, col]
        ax2.plot(x.index, x.RSI14, color="#7b3fa0", lw=0.7)
        for lvl, c in ((30, "#2ca02c"), (70, "#d62728")):
            ax2.axhline(lvl, color=c, ls=":", lw=0.9)
        ax2.set_ylim(5, 100); ax2.set_ylabel("RSI(14)"); ax2.grid(alpha=0.25)
    fig.tight_layout(); fig.savefig(out / "rsi30_trades_oos.png", dpi=125); plt.close(fig)
    return res


def export_json(df: pd.DataFrame, sel: pd.DataFrame, res: dict, out: Path, rules: list[str]):
    """JSON con el mismo espiritu que docs/semis8/semis8.json, para una pagina docs/rsi30/."""
    blob = {"generated_at": pd.Timestamp.now("UTC").isoformat(), "cost": COST, "cash_rate": CASH,
            "last_bar": {f"{t}_{tf}": str(d[rules[0]][0].index[-1].date()) for (t, tf), d in res.items()},
            "rules_shown": rules,
            "method": "Senal RSI14<=30 al cierre, ejecucion apertura siguiente; parametros elegidos con la primera mitad (IS), segunda mitad (OOS) aparte",
            "series": {}}
    for (t, tf), d in res.items():
        k = f"{t}_{tf}"
        eq, b, marks, split, trades = d[rules[0]]
        step = 1 if tf == "1w" else 5
        blob["series"][k] = {
            "split": str(split.date()),
            "dates": [str(i.date()) for i in eq.index[::step]],
            "equity": [round(float(v), 4) for v in eq.values[::step]],
            "bh_equity": [round(float(v), 4) for v in b.values[::step]],
            "trades": [{kk: (round(float(vv), 4) if isinstance(vv, (float, np.floating)) else vv) for kk, vv in tr.items()} for tr in trades],
            "stats": df[(df.asset == t) & (df.tf == tf) & (df.rule.isin(rules + ["Buy & hold"])) & (~df.scale_in)]
                     [["half", "rule", "CAGR", "Sharpe", "MaxDD", "TimeInMarket", "Trades", "WinRate"]]
                     .round(4).replace({np.nan: None}).to_dict("records"),
        }
    blob["selection"] = sel.round(4).replace({np.nan: None}).to_dict("records")
    (out / "rsi30.json").write_text(json.dumps(_clean_json(blob), ensure_ascii=False, allow_nan=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent))
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--cash", choices=["flat", "irx"], default="flat",
                    help="flat = cash_rate_annual de settings.yaml; irx = letra del Tesoro a 13 semanas")
    ap.add_argument("--site", action="store_true",
                    help="modo web (dashboard.yml): solo escribe rsi30.json en --out, sin CSV ni PNG, "
                         "con la cache de precios en data/cache/rsi30 (fuera de docs/)")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    cache = (ROOT or Path.cwd()) / "data" / "cache" / "rsi30" if a.site else None
    df, series, sims, errors = run(out, a.refresh or a.site, a.cash, cache)
    if errors:
        print("errores:", errors)
    if a.site:
        sel = select_rules(df)
        best = sel[sel.tf == "1d"].rule.iloc[0]
        alt = "RSI>50 y ganancia>=10%" if best != "RSI>50 y ganancia>=10%" else "RSI>70 y trailing 20%"
        export_json(df, sel, simulate_shown(series, [best, alt]), out, [best, alt])
        print("regla elegida en IS:", best, "| rsi30.json escrito en", out)
        return
    name = "rsi30_results.csv" if a.cash == "flat" else "rsi30_results_irx.csv"
    df.to_csv(out / name, index=False, float_format="%.6f")
    print(f"wrote {out / name} ({len(df)} filas); coste {COST}, cash {CASH if a.cash == 'flat' else '^IRX'}")
    print("errores:", errors)
    sel = select_rules(df)
    sel.to_csv(out / name.replace("results", "selection"), index=False, float_format="%.4f")
    best = sel[sel.tf == "1d"].rule.iloc[0]
    print("regla elegida en IS (diario, mejor rango medio en BTC/SPY/oro):", best)
    print(sel[["tf", "rule", "IS_mean_rank", "IS_mean_sharpe", "OOS_mean_sharpe", "OOS_mean_rank", "IS_trades", "OOS_trades", "BH_OOS_mean_sharpe"]]
          .groupby("tf").head(6).to_string(index=False))
    if a.cash == "flat":
        alt = "RSI>50 y ganancia>=10%" if best != "RSI>50 y ganancia>=10%" else "RSI>70 y trailing 20%"
        rules = [best, alt]
        res = make_charts(series, out, rules)
        export_json(df, sel, res, out, rules)
        print("graficos y rsi30.json escritos")


if __name__ == "__main__":
    main()
