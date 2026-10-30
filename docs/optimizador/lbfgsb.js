/* Sharpe Lab · máximo Sharpe y paridad de riesgo con L-BFGS-B.
 *
 * L-BFGS-B (Byrd, Lu, Nocedal y Zhu, 1995): cuasi-Newton de memoria limitada con
 * límites por variable l <= x <= u. Cada iteración:
 *   1. B ≈ Hessiana a partir de los últimos m pares (s, y) (BFGS sobre θI; con
 *      pocas variables se guarda densa, que es la misma matriz que la forma compacta);
 *   2. punto de Cauchy generalizado: primer mínimo del modelo cuadrático a lo largo
 *      del gradiente proyectado sobre la caja (recorriendo los puntos de ruptura);
 *   3. minimización en el subespacio de las variables libres y vuelta a la caja;
 *   4. búsqueda lineal (Armijo) y actualización de la memoria si sᵀy > 0.
 *
 * Las restricciones Σw = 1 y w_i <= c_i no son de caja. Se resuelven así:
 *   · Σw = 1: ambos objetivos son homogéneos, así que se optimiza z >= 0 y w = z/Σz.
 *     Máx. Sharpe:   min ½ zᵀΣz − μᵀz          (μ, Σ: exceso sobre el cash)
 *     Paridad:       min ½ zᵀΣz − (1/n) Σ log z_i   (Spinu, 2013)
 *     Sin límites, la primera da exactamente la cartera de máximo Sharpe y la
 *     segunda la de contribuciones al riesgo iguales.
 *   · w_i <= c_i  ⇔  z_i − c_i Σz <= 0 (lineal): Lagrangiano aumentado, con
 *     L-BFGS-B resolviendo cada subproblema con z >= 0 como caja.
 * Contrastado con scipy.optimize.minimize (L-BFGS-B y SLSQP) sobre los mismos datos.
 */
(function(root){
  'use strict';
  const dot=(a,b)=>{let s=0;for(let i=0;i<a.length;i++)s+=a[i]*b[i];return s;};
  const matvec=(M,x)=>M.map(r=>dot(r,x));

  // min f(x) con l <= x <= u. fg(x) -> [f, g]. Devuelve {x, f, iters, evals, conv}
  function lbfgsb(fg, x0, lo, hi, opt){
    opt=opt||{};
    const n=x0.length, m=opt.m||10, maxit=opt.maxit||3000, pgtol=opt.pgtol||1e-12, ftol=opt.ftol||1e-15;
    const L=i=>lo[i]==null?-Infinity:lo[i], U=i=>hi[i]==null?Infinity:hi[i];
    const proj=x=>x.map((v,i)=>Math.min(U(i),Math.max(L(i),v)));
    let x=proj(x0.slice()), [f,g]=fg(x), evals=1;
    const S=[], Y=[];
    const pgnorm=()=>{let mx=0;for(let i=0;i<n;i++){const p=Math.min(U(i),Math.max(L(i),x[i]-g[i]))-x[i];mx=Math.max(mx,Math.abs(p));}return mx;};
    function Bmat(){
      let th=1; if(S.length){const k=S.length-1; th=dot(Y[k],Y[k])/dot(S[k],Y[k]);}
      const B=Array.from({length:n},(_,i)=>{const r=new Array(n).fill(0); r[i]=th; return r;});
      for(let k=0;k<S.length;k++){
        const s=S[k], y=Y[k], Bs=matvec(B,s), sBs=dot(s,Bs), ys=dot(y,s);
        for(let i=0;i<n;i++) for(let j=0;j<n;j++) B[i][j]+= -Bs[i]*Bs[j]/sBs + y[i]*y[j]/ys;
      }
      return B;
    }
    function solve(A,b){ // eliminación gaussiana con pivoteo parcial (A pequeña)
      const k=b.length, M=A.map((r,i)=>r.concat([b[i]]));
      for(let c=0;c<k;c++){
        let p=c; for(let r=c+1;r<k;r++) if(Math.abs(M[r][c])>Math.abs(M[p][c])) p=r;
        if(Math.abs(M[p][c])<1e-300) return null;
        [M[c],M[p]]=[M[p],M[c]];
        for(let r=c+1;r<k;r++){const fct=M[r][c]/M[c][c]; if(fct) for(let q=c;q<=k;q++) M[r][q]-=fct*M[c][q];}
      }
      const out=new Array(k).fill(0);
      for(let r=k-1;r>=0;r--){let s=M[r][k]; for(let q=r+1;q<k;q++) s-=M[r][q]*out[q]; out[r]=s/M[r][r];}
      return out;
    }
    let it=0, conv='maxit';
    for(it=0; it<maxit; it++){
      if(pgnorm()<=pgtol){ conv='pgtol'; break; }
      const B=Bmat();
      // --- punto de Cauchy generalizado ---
      const tb=new Array(n), d=new Array(n);
      for(let i=0;i<n;i++){
        if(g[i]<0) tb[i]=U(i)===Infinity?Infinity:(x[i]-U(i))/g[i];
        else if(g[i]>0) tb[i]=L(i)===-Infinity?Infinity:(x[i]-L(i))/g[i];
        else tb[i]=Infinity;
        d[i]=tb[i]>0?-g[i]:0;
      }
      const order=[...Array(n).keys()].filter(i=>tb[i]>0&&tb[i]<Infinity).sort((a,b)=>tb[a]-tb[b]);
      const xc=x.slice(); let z=new Array(n).fill(0), told=0, oi=0;
      while(true){
        const Bd=matvec(B,d), fp=dot(g,d)+dot(z,Bd), fpp=dot(d,Bd);
        const tnext=oi<order.length?tb[order[oi]]:Infinity;
        if(fp>=0) break;
        const dtmin=fpp>0?-fp/fpp:Infinity;
        if(dtmin<tnext-told){ for(let i=0;i<n;i++){ z[i]+=dtmin*d[i]; } break; }
        if(tnext===Infinity) break; // modelo no acotado en esta dirección (no ocurre con B definida positiva)
        const dt=tnext-told; for(let i=0;i<n;i++) z[i]+=dt*d[i];
        // la(s) variable(s) que tocan su límite se fijan
        while(oi<order.length && tb[order[oi]]<=tnext){ const b=order[oi]; z[b]=(d[b]>0?U(b):L(b))-x[b]; d[b]=0; oi++; }
        told=tnext;
      }
      for(let i=0;i<n;i++) xc[i]=Math.min(U(i),Math.max(L(i),x[i]+z[i]));
      // --- minimización en el subespacio de variables libres ---
      const free=[]; for(let i=0;i<n;i++) if(xc[i]>L(i)&&xc[i]<U(i)) free.push(i);
      let xbar=xc.slice();
      if(free.length){
        const dxc=xc.map((v,i)=>v-x[i]), Bz=matvec(B,dxc);
        const r=free.map(i=>g[i]+Bz[i]);
        const du=solve(free.map(i=>free.map(j=>B[i][j])), r.map(v=>-v));
        if(du){
          let a=1; free.forEach((i,k)=>{ if(du[k]>0&&U(i)<Infinity) a=Math.min(a,(U(i)-xc[i])/du[k]); if(du[k]<0&&L(i)>-Infinity) a=Math.min(a,(L(i)-xc[i])/du[k]); });
          a=Math.max(0,a); free.forEach((i,k)=>{ xbar[i]=xc[i]+a*du[k]; });
        }
      }
      let dir=xbar.map((v,i)=>v-x[i]);
      let gd=dot(g,dir);
      if(!(gd<0)){ // dirección no de descenso: memoria fuera y gradiente proyectado
        S.length=0; Y.length=0;
        dir=proj(x.map((v,i)=>v-g[i])).map((v,i)=>v-x[i]); gd=dot(g,dir);
        if(!(gd<0)){ conv='pgtol'; break; }
      }
      // --- búsqueda lineal (Armijo con retroceso cuadrático) ---
      let step=1; if(it===0&&!S.length){ const nd=Math.sqrt(dot(dir,dir)); step=Math.min(1,1/nd); }
      let xn,fn,gn,ok=false;
      for(let ls=0; ls<60; ls++){
        xn=proj(x.map((v,i)=>v+step*dir[i])); [fn,gn]=fg(xn); evals++;
        if(isFinite(fn) && fn<=f+1e-4*step*gd){ ok=true; break; }
        const q=isFinite(fn)? -gd*step*step/(2*(fn-f-gd*step)) : step/10;
        step=Math.min(step/2, Math.max(step/10, q));
      }
      if(!ok){ conv='linesearch'; break; }
      const s=xn.map((v,i)=>v-x[i]), y=gn.map((v,i)=>v-g[i]), sy=dot(s,y);
      if(sy>2.2e-16*dot(y,y)){ S.push(s); Y.push(y); if(S.length>m){S.shift();Y.shift();} }
      const fold=f; x=xn; f=fn; g=gn;
      if((fold-f)/Math.max(Math.abs(fold),Math.abs(f),1)<=ftol){ conv='ftol'; it++; break; }
    }
    return {x, f, g, iters:it, evals, conv};
  }

  // min f0(z), z >= lb, con z_i − c_i Σz <= 0 (Lagrangiano aumentado; L-BFGS-B dentro)
  function capped(f0, n, caps, z0, lb){
    let lam=new Array(n).fill(0), rho=10, z=z0.slice(), inner=0, prev=Infinity, outer=0, viol=0;
    const h=z=>{const s=z.reduce((a,b)=>a+b,0); return z.map((v,i)=>v-caps[i]*s);};
    for(outer=0; outer<60; outer++){
      const lagr=z=>{
        const [f,g]=f0(z), hz=h(z); let pen=0; const t=hz.map((v,i)=>Math.max(0,lam[i]+rho*v));
        t.forEach((v,i)=>{pen+=v*v-lam[i]*lam[i];});
        const ct=dot(caps,t); const gg=g.map((v,j)=>v+t[j]-ct);   // Aᵀt con A = I − c·1ᵀ
        return [f+pen/(2*rho), gg];
      };
      const r=lbfgsb(lagr, z, z.map(()=>lb), z.map(()=>null), {});
      z=r.x; inner+=r.iters;
      const hz=h(z), s=z.reduce((a,b)=>a+b,0);
      viol=Math.max(0,...hz)/Math.max(s,1e-300);
      lam=lam.map((l,i)=>Math.max(0,l+rho*hz[i]));
      if(viol<1e-11 && outer>0) break;
      if(viol>0.25*prev) rho*=10;
      prev=viol;
    }
    return {z, outer:outer+1, inner, viol};
  }
  // recorta a [0, c] y reparte el resto (reparación numérica final, del orden de 1e-12)
  function projCaps(w, caps){
    w=w.map((v,i)=>Math.min(caps[i],Math.max(0,v)));
    for(let k=0;k<50;k++){
      const r=1-w.reduce((a,b)=>a+b,0); if(Math.abs(r)<1e-15) break;
      const room=w.map((v,i)=>r>0?caps[i]-v:v), tot=room.reduce((a,b)=>a+(b>1e-15?b:0),0); if(tot<=0) break;
      w=w.map((v,i)=>room[i]>1e-15?Math.min(caps[i],Math.max(0,v+r*room[i]/tot)):v);
    }
    return w;
  }
  function moments(cols){ // cols: n series diarias (%). Media y covarianza poblacional (como np.cov(bias=True))
    const n=cols.length, S=cols[0].length, mu=cols.map(c=>{let a=0;for(let s=0;s<S;s++)a+=c[s];return a/S;});
    const C=Array.from({length:n},()=>new Array(n).fill(0));
    for(let i=0;i<n;i++) for(let j=i;j<n;j++){ let a=0; const ci=cols[i], cj=cols[j], mi=mu[i], mj=mu[j]; for(let s=0;s<S;s++) a+=(ci[s]-mi)*(cj[s]-mj); C[i][j]=C[j][i]=a/S; }
    return {mu, C};
  }
  // xcols: rentabilidades diarias en exceso del cash (%) de los activos con riesgo
  function maxSharpe(xcols, caps){
    const n=xcols.length, {mu, C}=moments(xcols);
    if(mu.every(v=>v<=0)) return null;
    const f0=z=>{const Cz=matvec(C,z); return [0.5*dot(z,Cz)-dot(mu,z), Cz.map((v,i)=>v-mu[i])];};
    const r=capped(f0, n, caps, new Array(n).fill(1e-3), 0);
    const s=r.z.reduce((a,b)=>a+b,0); if(!(s>0)) return null;
    const w=projCaps(r.z.map(v=>v/s), caps);
    return {w, outer:r.outer, inner:r.inner, viol:r.viol, mu, C};
  }
  function riskParity(cols, caps){
    const n=cols.length, {C}=moments(cols), b=1/n;
    const f0=z=>{const Cz=matvec(C,z); let lg=0; for(const v of z) lg+=Math.log(v); return [0.5*dot(z,Cz)-b*lg, Cz.map((v,i)=>v-b/z[i])];};
    let sd=0; for(let i=0;i<n;i++) sd+=C[i][i]; sd=Math.sqrt(sd/n);
    const r=capped(f0, n, caps, new Array(n).fill(1/(sd*n)), 1e-12);
    const s=r.z.reduce((a,b)=>a+b,0);
    const w=projCaps(r.z.map(v=>v/s), caps);
    return {w, outer:r.outer, inner:r.inner, viol:r.viol, C, rc:rcShares(w,C)};
  }
  function rcShares(w, C){ const Cw=matvec(C,w), V=dot(w,Cw); return w.map((v,i)=>v*Cw[i]/V); }

  root.LBFGSB = { lbfgsb, capped, maxSharpe, riskParity, rcShares, moments, projCaps };
})(typeof window !== 'undefined' ? window : globalThis);
