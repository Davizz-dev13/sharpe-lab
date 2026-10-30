/* Sharpe Lab · optimizador de mínimo CVaR (Rockafellar–Uryasev) sobre TODOS los escenarios.
 *
 * Problema (LP de Rockafellar–Uryasev, S escenarios equiprobables = días de la ventana):
 *   min_{w,a,u}  a + 1/(S·beta) · Σ_s u_s
 *   s.a.  u_s >= -r_s·w - a,  u_s >= 0        (s = 1..S)
 *         Σ_i w_i = 1,  0 <= w_i <= c_i,  μ·w >= m   (o = m para la rama ineficiente)
 *
 * Se resuelve con el método de planos de corte de Künzi-Bay y Mayer (2006), que
 * da el MISMO óptimo que el LP completo pero sin S variables auxiliares:
 *   CVaR_beta(w) = max { Σ_s q_s L_s(w) : 0 <= q_s <= 1/(S·beta), Σ q_s = 1 },
 * con L_s(w) = -r_s·w. Para un w dado, el q que maximiza pone 1/(S·beta) en las
 * peores pérdidas (y la fracción restante en la siguiente), lo que da un corte
 * lineal t >= g·w válido para todo w. El LP maestro (n+1 variables) se resuelve
 * con el símplex de vendor/solver.js y se itera hasta que la cota inferior (t del
 * maestro) y la superior (CVaR exacto del iterado) difieren menos de la tolerancia.
 * Como los cortes son válidos para cualquier w, se reutilizan entre puntos de la
 * frontera.
 *
 * Unidades: rentabilidades diarias en %, μ en % anual (media aritmética × días/año).
 */
(function(root){
  'use strict';
  const SHIFT = 100;  // t + SHIFT >= 0 (las variables del símplex son no negativas)

  // CVaR_beta exacto (definición de Rockafellar–Uryasev con fracción) de una serie de rentabilidades en %.
  function cvarOf(p, beta){
    const S = p.length, k = S*beta, f = Math.floor(k);
    const L = Float64Array.from(p, x => -x).sort().reverse();
    let s = 0; for(let j=0;j<f;j++) s += L[j];
    if(f < S) s += (k-f)*L[f];
    return s/k;
  }
  function portSeries(cols, w){
    const S = cols[0].length, out = new Float64Array(S);
    for(let i=0;i<cols.length;i++){ const wi=w[i]; if(!wi) continue; const c=cols[i]; for(let s=0;s<S;s++) out[s]+=wi*c[s]; }
    return out;
  }
  // Corte de Künzi-Bay–Mayer en w: devuelve g con CVaR(w') >= g·w' para todo w' y CVaR(w) = g·w.
  function cutAt(cols, w, beta){
    const S = cols[0].length, n = cols.length;
    const p = portSeries(cols, w);
    const idx = Array.from({length:S}, (_,s)=>s).sort((a,b)=>p[a]-p[b]);  // peores primero
    const k = S*beta, f = Math.floor(k), qa = 1/k;
    const g = new Float64Array(n);
    const add = (s, q) => { for(let i=0;i<n;i++) g[i] -= q*cols[i][s]; };
    for(let j=0;j<f;j++) add(idx[j], qa);
    if(f < S && k > f) add(idx[f], (k-f)*qa);
    let val = 0; for(let i=0;i<n;i++) val += g[i]*w[i];
    return { g: Array.from(g), val };
  }

  function make(cols, mu, caps, beta, rfdDef, rfaDef){
    const n = cols.length;
    const cuts = [];
    const pushCut = c => { cuts.push(c.g); };
    // cortes iniciales: cartera equiponderada y cada vértice "llenar hasta el límite por orden de μ"
    const eq = Array(n).fill(1/n);
    pushCut(cutAt(cols, eq, beta));

    function master(target, mode){
      const constraints = { sumw: { equal: 1 } };
      const variables = { T: { obj: 1 } };
      for(let i=0;i<n;i++){
        const v = { obj: 0, sumw: 1 };
        constraints['cap'+i] = { max: caps[i] }; v['cap'+i] = 1;
        if(mode){ v.ret = mu[i]; }
        variables['w'+i] = v;
      }
      if(mode === 'ge') constraints.ret = { min: target };
      if(mode === 'eq') constraints.ret = { equal: target };
      cuts.forEach((g,j)=>{
        constraints['c'+j] = { min: SHIFT };
        variables.T['c'+j] = 1;
        for(let i=0;i<n;i++) variables['w'+i]['c'+j] = -g[i];
      });
      const res = root.solver.Solve({ optimize:'obj', opType:'min', constraints, variables });
      if(!res.feasible || !isFinite(res.result)) return null;
      const w = []; for(let i=0;i<n;i++) w.push(Math.max(0, res['w'+i] || 0));
      return { w, lb: (res.T || 0) - SHIFT };
    }

    function clean(w){
      // reparación numérica mínima: recorta a [0, c_i] y renormaliza a Σw = 1
      let s = 0; const x = w.map((v,i)=>Math.min(caps[i], Math.max(0, v))); x.forEach(v=>s+=v);
      return x.map(v=>v/s);
    }

    // min CVaR s.a. μ·w (>= | =) target   (mode null: sin restricción de rentabilidad)
    function minCVaR(target, mode, tol){
      tol = tol || 1e-7;
      let best = null;
      for(let it=0; it<300; it++){
        const m = master(target, mode);
        if(!m) return null;
        const w = clean(m.w);
        const c = cutAt(cols, w, beta);
        if(!best || c.val < best.cvar) best = { w, cvar: c.val, it };
        if(best.cvar - m.lb <= tol*(1+Math.abs(best.cvar))) { best.gap = best.cvar - m.lb; best.iters = it+1; return best; }
        pushCut(c);
      }
      best.iters = 300; best.gap = NaN; return best;
    }

    // Cartera tangente vista desde el punto (CVaR, μ) = (-d, a): max (μ·w - a)/(CVaR(w) + d) sobre la región factible.
    // Por defecto (d, a) = (rf_d, rf_a); el optimizador usa el ancla de la «Recomendada»: (0, r0), con r0 = μ del Mín. CVaR (objetivo).
    // Charnes–Cooper: y = κw, κ >= 0 ⇒ LP  min CVaR(y) + d·κ  s.a. (μ - a)·y = 1,
    // Σy = κ, 0 <= y_i <= c_i·κ  (el CVaR es positivamente homogéneo, así que los mismos cortes valen).
    function tangency(tol, anchor){
      tol = tol || 1e-8;
      const rfd = anchor ? anchor.d : rfdDef, rfa = anchor ? anchor.a : rfaDef;
      let best = null;
      for(let it=0; it<300; it++){
        const constraints = { exc: { equal: 1 }, sumk: { equal: 0 }, kmax: { max: 1e6 } };
        const variables = { T: { obj: 1 }, k: { obj: rfd - SHIFT, sumk: -1, kmax: 1 } };
        for(let i=0;i<n;i++){
          const v = { obj: 0, exc: mu[i]-rfa, sumk: 1 };
          constraints['cap'+i] = { max: 0 }; v['cap'+i] = 1; variables.k['cap'+i] = -caps[i];
          variables['y'+i] = v;
        }
        cuts.forEach((g,j)=>{
          constraints['c'+j] = { min: 0 };
          variables.T['c'+j] = 1; variables.k['c'+j] = -SHIFT;
          for(let i=0;i<n;i++) variables['y'+i]['c'+j] = -g[i];
        });
        const res = root.solver.Solve({ optimize:'obj', opType:'min', constraints, variables });
        if(!res.feasible || !isFinite(res.result)) return null;
        const k = res.k || 0; if(!(k > 0)) return null;
        const y = []; for(let i=0;i<n;i++) y.push(Math.max(0, res['y'+i]||0));
        const w = clean(y.map(v=>v/k));
        const c = cutAt(cols, w, beta);
        const lbDen = res.result;                     // cota inferior de min (CVaR(y)+rf_d κ) con exceso = 1
        const ratio = (dot(mu,w) - rfa)/(c.val + rfd); // valor exacto del iterado
        if(!best || ratio > best.ratio) best = { w, ratio, cvar: c.val, it };
        // max ratio <= 1/lbDen
        if(1/lbDen - best.ratio <= tol*(1+Math.abs(best.ratio))) { best.iters = it+1; best.gap = 1/lbDen - best.ratio; return best; }
        pushCut(c);
      }
      best.iters = 300; best.gap = NaN; return best;
    }
    return { minCVaR, tangency, cuts };
  }
  function dot(a,b){ let s=0; for(let i=0;i<a.length;i++) s+=a[i]*b[i]; return s; }

  root.CVaRLP = { cvarOf, portSeries, cutAt, make, dot };
})(typeof window !== 'undefined' ? window : globalThis);
