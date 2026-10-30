#!/usr/bin/env python3
"""Test fuera de muestra (walk-forward) de los objetivos del optimizador de docs/optimizador/.

Compara Mín. CVaR (μ >= objetivo, el de la página), Mín. CVaR sin cash, tangente CVaR,
Máx. Sharpe y paridad de riesgo (L-BFGS-B, sin cash) y 1/N, con el universo y los límites por
defecto de la página, sobre docs/optimizador/optimizador-long.json:
  el último día de cada mes se estima con los N años anteriores, se fijan los pesos y se
  mantienen (con deriva) hasta el siguiente rebalanceo. Métricas solo fuera de muestra.

Uso:  pip install scipy pandas  &&  python scripts/test_optimizadores.py [--years 3] [--freq M] [--coste 0]
No forma parte del workflow nocturno.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import linprog, minimize
from scipy.sparse import csr_matrix, eye, hstack, vstack

ROOT = Path(__file__).resolve().parents[1]
INC = {"Cash": 1.00, "Gold": .30, "Commodities": .30, "S&P 500": .30, "Bitcoin": .15, "MSCI World": .30, "Emerging": .30}
BETA, TARGET = 0.05, 5.0

def proj_caps(w, caps):
    """Recorta a [0, c] y reparte el resto entre los que tienen hueco (reparación numérica final)."""
    w = np.clip(w, 0, caps)
    for _ in range(50):
        r = 1 - w.sum()
        if abs(r) < 1e-15:
            break
        room = (caps - w) if r > 0 else w
        idx = room > 1e-15
        if not idx.any():
            break
        w[idx] += r * room[idx] / room[idx].sum()
        w = np.clip(w, 0, caps)
    return w


def al_solve(f0, n, caps, z0, lb=0.0, tol=1e-11):
    """min f0(z) con z >= lb (caja, L-BFGS-B) y z_i - c_i·Σz <= 0 (Lagrangiano aumentado)."""
    lam = np.zeros(n); rho = 10.0; z = z0.copy(); prev = np.inf
    A = np.eye(n) - np.outer(caps, np.ones(n))

    def L(z):
        f, g = f0(z); h = A @ z; t = np.maximum(0, lam + rho * h)
        return f + ((t ** 2).sum() - (lam ** 2).sum()) / (2 * rho), g + A.T @ t
    for outer in range(60):
        r = minimize(L, z, jac=True, method="L-BFGS-B", bounds=[(lb, None)] * n,
                     options=dict(ftol=1e-16, gtol=1e-13, maxiter=5000, maxcor=10))
        z = r.x; h = A @ z
        viol = np.maximum(0, h).max() / max(z.sum(), 1e-300)
        lam = np.maximum(0, lam + rho * h)
        if viol < tol and outer > 0:
            break
        if viol > 0.25 * prev:
            rho *= 10
        prev = viol
    return z


def max_sharpe(X, caps):
    """X: S x n rentabilidades diarias en exceso del cash (%). min ½zᵀΣz − μᵀz, z>=0, w = z/Σz."""
    mu = X.mean(0); Sig = np.cov(X, rowvar=False, bias=True); n = len(caps)
    if (mu <= 0).all():
        return None
    z = al_solve(lambda z: (0.5 * z @ Sig @ z - mu @ z, Sig @ z - mu), n, caps, np.full(n, 1e-3))
    return proj_caps(z / z.sum(), caps)


def risk_parity(C, caps):
    """C: S x n rentabilidades diarias (%). min ½zᵀΣz − (1/n)Σlog z_i, z>0, w = z/Σz (Spinu)."""
    Sig = np.cov(C, rowvar=False, bias=True); n = len(caps); b = 1 / n
    z0 = np.full(n, 1 / np.sqrt(np.diag(Sig).mean()) / n)
    z = al_solve(lambda z: (0.5 * z @ Sig @ z - b * np.log(z).sum(), Sig @ z - b / z), n, caps, z0, lb=1e-12)
    return proj_caps(z / z.sum(), caps)


def rc_shares(w, Sig):
    Sw = Sig @ w
    return w * Sw / (w @ Sw)


def cvar(p, beta):
    L = np.sort(-p)[::-1]; k = len(p) * beta; f = int(np.floor(k))
    return (L[:f].sum() + (k - f) * (L[f] if f < len(L) else 0.0)) / k


def min_cvar(R, mu, caps, beta, m=None):
    S, N = R.shape
    c = np.r_[np.zeros(N), 1.0, np.full(S, 1 / (S * beta))]
    A = hstack([csr_matrix(-R), -np.ones((S, 1)), -eye(S)]).tocsr(); b = np.zeros(S)
    if m is not None:
        A = vstack([A, csr_matrix(np.r_[-mu, 0, np.zeros(S)][None, :])]).tocsr(); b = np.r_[b, -m]
    bd = [(0, cp) for cp in caps] + [(None, None)] + [(0, None)] * S
    r = linprog(c, A_ub=A, b_ub=b, A_eq=np.r_[np.ones(N), 0, np.zeros(S)][None, :], b_eq=[1], bounds=bd, method="highs")
    return None if r.status != 0 else proj_caps(np.maximum(r.x[:N], 0), caps)


def tangency(R, mu, caps, beta, rfa, rfd):
    S, N = R.shape
    c = np.r_[np.zeros(N), rfd, 1.0, np.full(S, 1 / (S * beta))]
    A1 = hstack([csr_matrix(-R), csr_matrix((S, 1)), -np.ones((S, 1)), -eye(S)])
    A2 = hstack([eye(N), csr_matrix(-caps.reshape(-1, 1)), csr_matrix((N, 1)), csr_matrix((N, S))])
    Aeq = np.zeros((2, N + 2 + S)); Aeq[0, :N] = mu - rfa; Aeq[1, :N] = 1; Aeq[1, N] = -1
    bd = [(0, None)] * (N + 1) + [(None, None)] + [(0, None)] * S
    r = linprog(c, A_ub=vstack([A1, A2]).tocsr(), b_ub=np.zeros(S + N), A_eq=Aeq, b_eq=[1, 0], bounds=bd, method="highs")
    return None if r.status != 0 or r.x[N] <= 0 else proj_caps(r.x[:N] / r.x[N], caps)


def max_mean(mu, caps):
    w = np.zeros(len(caps)); rem = 1.0
    for i in np.argsort(-mu):
        w[i] = min(caps[i], rem); rem -= w[i]
    return w


def dpy(idx):
    return (len(idx) - 1) / ((idx[-1] - idx[0]).days / 365.25)


def weights(win, names):
    C = win.values * 100; caps = np.array([INC[s] for s in names]); mu = C.mean(0) * dpy(win.index)
    ci = names.index("Cash"); ri = [i for i in range(len(names)) if i != ci]
    rfd = C[:, ci].mean(); rfa = rfd * dpy(win.index)
    full = lambda w: (lambda f: (f.__setitem__(ri, w), f)[1])(np.zeros(len(names)))
    out = {}
    whi = max_mean(mu, caps)
    if TARGET > mu @ whi:
        out["Mín. CVaR (μ ≥ 5 %)"] = whi
    else:
        g = min_cvar(C, mu, caps, BETA)
        out["Mín. CVaR (μ ≥ 5 %)"] = g if TARGET <= mu @ g else min_cvar(C, mu, caps, BETA, min(TARGET, mu @ whi - 1e-7))
    out["Mín. CVaR sin cash"] = full(min_cvar(C[:, ri], mu[ri], caps[ri], BETA))
    t = tangency(C, mu, caps, BETA, rfa, rfd)
    out["Tangente CVaR"] = t if t is not None else out["Mín. CVaR (μ ≥ 5 %)"]
    ms = max_sharpe(C[:, ri] - C[:, [ci]], caps[ri])
    out["Máx. Sharpe (L-BFGS-B)"] = full(ms) if ms is not None else np.eye(len(names))[ci]
    out["Paridad de riesgo (L-BFGS-B)"] = full(risk_parity(C[:, ri], caps[ri]))
    out["1/N (sin cash)"] = full(np.full(len(ri), 1 / len(ri)))
    return out


def stats(r, rf, turns):
    yrs = (r.index[-1] - r.index[0]).days / 365.25 + 1 / 365.25; d = len(r) / yrs
    eq = (1 + r).cumprod(); x = r - rf
    return {"CAGR %": (eq.iloc[-1] ** (1 / yrs) - 1) * 100, "Vol %": r.std() * np.sqrt(d) * 100,
            "Sharpe": x.mean() / x.std() * np.sqrt(d), "Máx. DD %": (eq / eq.cummax() - 1).min() * 100,
            "CVaR95 diario %": cvar(r.values * 100, .05), "Rotación anual %": sum(turns) / yrs * 100}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=float, default=3); ap.add_argument("--freq", default="M")
    ap.add_argument("--coste", type=float, default=0.0, help="pb por unidad negociada")
    a = ap.parse_args()
    D = json.load(open(ROOT / "docs" / "optimizador" / "optimizador-long.json"))
    t = {x["short"]: x["ticker"] for x in D["assets"]}
    R = pd.DataFrame({s: [np.nan if v is None else v for v in D["returns"][t[s]]] for s in INC}, index=pd.to_datetime(D["dates"]))
    idx = R.index; per = idx.to_period(a.freq)
    reb = [idx[i] for i in range(len(idx) - 1) if per[i] != per[i + 1]]
    rets, turns, cur, days = {}, {}, {}, []
    for k, d in enumerate(reb):
        lo = d - pd.DateOffset(years=int(a.years), months=int(round((a.years % 1) * 12)))
        if lo < idx[0]:
            continue
        win = R[(R.index > lo) & (R.index <= d)]
        if win.isna().any().any():
            continue            # todos los activos con historia completa en la ventana
        names = list(R.columns); W = weights(win, names)
        hold = R[(R.index > d) & (R.index <= (reb[k + 1] if k + 1 < len(reb) else idx[-1]))].values
        for m, wt in W.items():
            prev = cur.get(m); tv = np.abs(wt - prev).sum() / 2 if prev is not None else 0.0
            turns.setdefault(m, []).append(tv); w = wt.copy()
            for j, h in enumerate(hold):
                r = w @ h - (a.coste / 1e4 * 2 * tv if j == 0 else 0)
                rets.setdefault(m, []).append(r); w = w * (1 + h); w /= w.sum()
            cur[m] = w
        days.extend(R.index[(R.index > d) & (R.index <= (reb[k + 1] if k + 1 < len(reb) else idx[-1]))])
    days = pd.DatetimeIndex(days); rf = R["Cash"].reindex(days)
    T = pd.DataFrame({m: stats(pd.Series(v, index=days), rf, turns[m]) for m, v in rets.items()}).T
    print(f"Fuera de muestra: {days[0].date()} a {days[-1].date()} ({len(days)} días) · ventana {a.years:g} años · rebalanceo {a.freq}")
    print(T.round(2).to_string())


if __name__ == "__main__":
    main()
