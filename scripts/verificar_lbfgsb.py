#!/usr/bin/env python3
"""Verificación independiente de Máx. Sharpe y paridad de riesgo (L-BFGS-B) de docs/optimizador/.

Con el universo y los límites por defecto de la página y la ventana de 5 años
(docs/optimizador/optimizador.json), resuelve:
  - la misma formulación que la página (z >= 0 como caja de L-BFGS-B, límites w_i <= c_i con
    Lagrangiano aumentado) con scipy.optimize.minimize(method="L-BFGS-B");
  - el problema original con restricciones explícitas (Σw = 1, 0 <= w_i <= c_i) con SLSQP.
Imprime los pesos de ambos, la diferencia máxima y las contribuciones al riesgo de la paridad.
Los pesos deben coincidir con los de la página (pestaña «Objetivo»).

Uso:  pip install scipy  &&  python scripts/verificar_lbfgsb.py
No forma parte del workflow nocturno.
"""
from __future__ import annotations
import json
from datetime import date
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[1]
INC = {"Cash": 1.00, "Gold": .30, "Commodities": .30, "S&P 500": .30, "Bitcoin": .15, "MSCI World": .30, "Emerging": .30}

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


def main():
    D = json.load(open(ROOT / "docs" / "optimizador" / "optimizador.json"))
    t = {x["short"]: x["ticker"] for x in D["assets"]}
    dates = D["dates"]; n = len(dates)
    dpy = (n - 1) / ((date.fromisoformat(dates[-1]) - date.fromisoformat(dates[0])).days / 365.25)
    rf = np.array([v or 0.0 for v in D["returns"]["BIL"]]) * 100
    names = [s for s in INC if s != "Cash"]; caps = np.array([INC[s] for s in names])
    C = np.array([[v or 0.0 for v in D["returns"][t[s]]] for s in names]).T * 100
    X = C - rf[:, None]
    mu = X.mean(0); Sx = np.cov(X, rowvar=False, bias=True); S = np.cov(C, rowvar=False, bias=True)
    sharpe = lambda w: mu @ w / np.sqrt(w @ Sx @ w) * np.sqrt(dpy)
    cons = [{"type": "eq", "fun": lambda w: w.sum() - 1}]

    w_lb = max_sharpe(X, caps)
    best = None
    for k in range(len(names) + 1):
        x0 = proj_caps(np.full(len(names), 1 / len(names)) if k == 0 else np.eye(len(names))[k - 1] + .01, caps)
        r = minimize(lambda w: -sharpe(w), x0 / x0.sum(), method="SLSQP", bounds=[(0, c) for c in caps],
                     constraints=cons, options=dict(ftol=1e-14, maxiter=1000))
        if best is None or r.fun < best.fun:
            best = r
    w_sl = best.x
    print(f"Ventana {dates[0]} a {dates[-1]} ({n} días) · activos con riesgo: {', '.join(names)}")
    print("\nMáx. Sharpe (sin cash, con límites):")
    for s, a, b in zip(names, w_lb, w_sl):
        print(f"  {s:12s} L-BFGS-B {a*100:7.3f} %   SLSQP {b*100:7.3f} %")
    print(f"  Sharpe {sharpe(w_lb):.4f} (L-BFGS-B) / {sharpe(w_sl):.4f} (SLSQP) · dif. máx. {np.abs(w_lb-w_sl).max()*100:.5f} pp")

    w_rp = risk_parity(C, caps)
    Sg = S; nn = len(caps)
    rr = minimize(lambda z: 0.5 * z @ Sg @ z - np.log(z).sum() / nn, np.full(nn, .1), jac=lambda z: Sg @ z - 1 / (nn * z),
                  method="SLSQP", bounds=[(1e-10, None)] * nn,
                  constraints=[{"type": "ineq", "fun": (lambda z, i=i: caps[i] * z.sum() - z[i])} for i in range(nn)],
                  options=dict(ftol=1e-16, maxiter=2000))
    w_rp2 = rr.x / rr.x.sum()
    print("\nParidad de riesgo (sin cash, con límites):")
    for s, a, b, c in zip(names, w_rp, w_rp2, rc_shares(w_rp, S)):
        print(f"  {s:12s} L-BFGS-B {a*100:7.3f} %   SLSQP {b*100:7.3f} %   contribución al riesgo {c*100:6.2f} %")
    print(f"  dif. máx. {np.abs(w_rp-w_rp2).max()*100:.5f} pp")


if __name__ == "__main__":
    main()
