#!/usr/bin/env python3
"""Verificación independiente del optimizador de mínimo CVaR de docs/optimizador/.

Resuelve con HiGHS (scipy) el LP COMPLETO de Rockafellar–Uryasev sobre todos los días
de docs/optimizador/optimizador.json, con el universo y los límites por defecto de la
página, y comprueba las propiedades de la frontera:
  - pesos >= 0, <= límite y que suman 1;
  - v(m) convexa en m (frontera cóncava en el plano CVaR–μ);
  - la cartera tangente (Charnes–Cooper) maximiza (μ - r_f)/(CVaR + r_f^d) sobre la frontera
    y ningún punto de la frontera queda por encima de la recta desde r_f.
Los números que imprime deben coincidir con los de la página (mismo CVaR, misma μ).

Uso:  pip install scipy  &&  python scripts/verificar_optimizador.py [--beta 0.05]
No forma parte del workflow nocturno.
"""
from __future__ import annotations
import argparse, json
from datetime import date
from pathlib import Path

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import csr_matrix, eye, hstack, vstack

ROOT = Path(__file__).resolve().parents[1]
INC = {"Cash": 1.00, "Gold": .30, "Commodities": .30, "S&P 500": .30, "Bitcoin": .15, "MSCI World": .30, "Emerging": .30}


def cvar(p, beta):
    L = np.sort(-p)[::-1]; k = len(p) * beta; f = int(np.floor(k))
    return (L[:f].sum() + (k - f) * (L[f] if f < len(L) else 0.0)) / k


def min_cvar(R, mu, caps, beta, m=None):
    S, N = R.shape
    c = np.r_[np.zeros(N), 1.0, np.full(S, 1 / (S * beta))]
    A = hstack([csr_matrix(-R), -np.ones((S, 1)), -eye(S)]).tocsr()
    Aeq, beq = [np.r_[np.ones(N), 0, np.zeros(S)]], [1.0]
    if m is not None:
        Aeq.append(np.r_[mu, 0, np.zeros(S)]); beq.append(m)
    b = [(0, cp) for cp in caps] + [(None, None)] + [(0, None)] * S
    r = linprog(c, A_ub=A, b_ub=np.zeros(S), A_eq=np.array(Aeq), b_eq=beq, bounds=b, method="highs")
    return r.x[:N], r.fun


def tangency(R, mu, caps, beta, rfd, rfa):
    S, N = R.shape
    c = np.r_[np.zeros(N), rfd, 1.0, np.full(S, 1 / (S * beta))]
    A1 = hstack([csr_matrix(-R), csr_matrix((S, 1)), -np.ones((S, 1)), -eye(S)])
    A2 = hstack([eye(N), csr_matrix(-caps.reshape(-1, 1)), csr_matrix((N, 1)), csr_matrix((N, S))])
    Aeq = np.zeros((2, N + 2 + S)); Aeq[0, :N] = mu - rfa; Aeq[1, :N] = 1; Aeq[1, N] = -1
    b = [(0, None)] * (N + 1) + [(None, None)] + [(0, None)] * S
    r = linprog(c, A_ub=vstack([A1, A2]).tocsr(), b_ub=np.zeros(S + N), A_eq=Aeq, b_eq=[1, 0], bounds=b, method="highs")
    return r.x[:N] / r.x[N], 1 / r.fun


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--beta", type=float, default=0.05); a = ap.parse_args()
    D = json.load(open(ROOT / "docs" / "optimizador" / "optimizador.json"))
    t = {x["short"]: x["ticker"] for x in D["assets"]}
    dates = D["dates"]; n = len(dates)
    dpy = (n - 1) / ((date.fromisoformat(dates[-1]) - date.fromisoformat(dates[0])).days / 365.25)
    names = list(INC); caps = np.array([INC[s] for s in names])
    R = np.array([[v or 0.0 for v in D["returns"][t[s]]] for s in names]).T * 100   # % diario
    mu = R.mean(0) * dpy                                                             # % anual (aritmética)
    rfd = float(np.mean([v or 0.0 for v in D["returns"]["BIL"]])) * 100; rfa = rfd * dpy
    print(f"Ventana {dates[0]} a {dates[-1]} ({n} días, {dpy:.2f} días/año) · r_f = {rfa:.3f} % anual · beta = {a.beta}")
    wg, vg = min_cvar(R, mu, caps, a.beta)
    order = np.argsort(-mu); whi = np.zeros(len(names)); rem = 1.0
    for i in order: whi[i] = min(caps[i], rem); rem -= whi[i]
    mg, mhi = mu @ wg, mu @ whi
    ms = np.linspace(mg, mhi - 1e-7, 41)
    pts = []
    for m in ms:
        w, v = min_cvar(R, mu, caps, a.beta, m)
        assert abs(w.sum() - 1) < 1e-7 and (w >= -1e-9).all() and (w <= caps + 1e-9).all()
        pts.append((m, v))
    v = np.array([p[1] for p in pts]); dv = np.diff(v) / np.diff(ms)
    print(f"Mín. CVaR global: CVaR {vg:.4f} %, μ {mg:.3f} % · máx. μ alcanzable {mhi:.3f} %")
    print(f"v(m) convexa: {bool((np.diff(dv) >= -1e-6).all())} (pendientes de {dv.min():.4f} a {dv.max():.4f})")
    wt, ratio = tangency(R, mu, caps, a.beta, rfd, rfa)
    rat = (ms - rfa) / (v + rfd)
    print(f"Tangente: μ {mu @ wt:.3f} %, CVaR {cvar(R @ wt, a.beta):.4f} %, ratio {ratio:.4f} · máx. ratio en la frontera {rat.max():.4f}")
    print(f"Máx. distancia de la frontera por encima de la recta: {np.max(ms - (rfa + ratio * (v + rfd))):.2e} (debe ser <= 0)")
    print("Pesos de la tangente:", {s: round(float(x), 4) for s, x in zip(names, wt) if x > 1e-4})


if __name__ == "__main__":
    main()
