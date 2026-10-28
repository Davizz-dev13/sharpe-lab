/* Sharpe Lab · analítica común para las páginas de estrategia.
 * Curva frente a benchmark, drawdown, Sharpe rodante de 12 meses y registro de
 * operaciones. Todo se calcula en el navegador a partir de las curvas que ya
 * generan los scripts (docs/*.json), con Chart.js (el mismo que usa la web).
 *
 * Uso:
 *   SLA.panel(el, {dates, series:[{label, equity, color, dash}], rf:0.02, note})
 *   SLA.trades(el, trades, {asset:false, filename:'operaciones.csv'})
 */
(function () {
  const MUTED = 'rgba(255,255,255,.56)', GRID = 'rgba(255,255,255,.08)';
  const DAY = 864e5;

  function ts(d) { return Date.parse(d + 'T00:00:00Z'); }

  // Barras por año reales de la serie (≈252 bolsa, ≈365 BTC, 52 semanal)
  function periodsPerYear(dates) {
    const yrs = (ts(dates[dates.length - 1]) - ts(dates[0])) / (365.25 * DAY);
    return yrs > 0 ? (dates.length - 1) / yrs : 252;
  }
  function returns(eq) {
    const r = [0];
    for (let i = 1; i < eq.length; i++) r.push(eq[i - 1] ? eq[i] / eq[i - 1] - 1 : 0);
    return r;
  }
  function drawdown(eq) {
    let peak = -Infinity;
    return eq.map(v => { if (v > peak) peak = v; return (v / peak - 1) * 100; });
  }
  // Sharpe de los últimos 12 meses en cada fecha, sobre el exceso frente a rf
  function rollingSharpe(dates, eq, rf) {
    const r = returns(eq), n = r.length, out = new Array(n).fill(null);
    const ppy = periodsPerYear(dates), rfb = rf / ppy;
    let j = 1, s = 0, s2 = 0, cnt = 0;
    for (let i = 1; i < n; i++) {
      const x = r[i] - rfb; s += x; s2 += x * x; cnt++;
      const from = ts(dates[i]) - 365 * DAY;
      while (j < i && ts(dates[j]) <= from) { const y = r[j] - rfb; s -= y; s2 -= y * y; cnt--; j++; }
      if (ts(dates[i]) - ts(dates[0]) < 365 * DAY || cnt < 10) continue;
      const m = s / cnt, v = (s2 - cnt * m * m) / (cnt - 1);
      out[i] = v > 1e-14 ? m / Math.sqrt(v) * Math.sqrt(ppy) : null;
    }
    return out;
  }
  function baseOpts(yTitle, opts = {}) {
    return {
      responsive: true, maintainAspectRatio: false, animation: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { labels: { color: MUTED, boxWidth: 12, font: { size: 11 } } },
        tooltip: { callbacks: { label: c => c.dataset.label + ': ' + (c.parsed.y == null ? '–' : c.parsed.y.toFixed(opts.dec ?? 2) + (opts.unit || '')) } }
      },
      scales: {
        x: { ticks: { color: MUTED, maxTicksLimit: opts.ticks || 6, maxRotation: 0, autoSkipPadding: 12,
               callback(v) { const l = this.getLabelForValue(v); return l ? l.slice(0, 7) : l; } }, grid: { color: GRID } },
        y: Object.assign({ ticks: { color: MUTED }, grid: { color: GRID }, title: { display: true, text: yTitle, color: MUTED } }, opts.y || {})
      }
    };
  }
  function ds(s, data, extra) {
    return Object.assign({ label: s.label, data, borderColor: s.color, borderWidth: s.width || 1.5,
      borderDash: s.dash || [], pointRadius: 0, tension: 0.1, spanGaps: true }, extra || {});
  }
  function el(tag, cls, html) { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; }

  const charts = new WeakMap();

  function panel(root, cfg) {
    const { dates, series } = cfg;
    const rf = cfg.rf == null ? 0.02 : cfg.rf;
    (charts.get(root) || []).forEach(c => c.destroy());
    root.innerHTML = '';
    if (!dates || dates.length < 30 || !series || !series.length) {
      root.appendChild(el('p', 'sla-note', 'Todavía no hay datos suficientes para estos gráficos.'));
      return;
    }
    const grid = el('div', 'sla-grid');
    const boxes = [['Curva frente al benchmark', 'sla-eq'], ['Drawdown', 'sla-dd'], ['Sharpe rodante (12 meses)', 'sla-rs']]
      .map(([t, id]) => { const b = el('div', 'sla-box'); b.appendChild(el('h3', 'sla-h', t)); const w = el('div', 'sla-wrap'); const c = document.createElement('canvas'); w.appendChild(c); b.appendChild(w); grid.appendChild(b); return c; });
    root.appendChild(grid);
    if (cfg.note) root.appendChild(el('p', 'sla-note', cfg.note));
    const made = [];
    const valid = series.filter(s => s.equity && s.equity.length === dates.length);
    made.push(new Chart(boxes[0], { type: 'line',
      data: { labels: dates, datasets: valid.map(s => ds(s, s.equity.map(v => v / s.equity[0]))) },
      options: baseOpts('Crecimiento de 1 (escala log)', { y: { type: 'logarithmic' }, dec: 2, ticks: 8 }) }));
    made.push(new Chart(boxes[1], { type: 'line',
      data: { labels: dates, datasets: valid.map((s, i) => ds(s, drawdown(s.equity), i === 0 ? { fill: 'origin', backgroundColor: 'rgba(223,140,112,.15)' } : {})) },
      options: baseOpts('Caída desde máximos (%)', { dec: 1, unit: ' %', ticks: 5 }) }));
    made.push(new Chart(boxes[2], { type: 'line',
      data: { labels: dates, datasets: valid.map(s => ds(s, rollingSharpe(dates, s.equity, rf))) },
      options: baseOpts('Sharpe 12 meses (exceso sobre cash)', { dec: 2, ticks: 5 }) }));
    charts.set(root, made);
  }

  function fmtP(v) { return v == null ? '–' : (v > 0 ? '+' : '') + v.toFixed(2).replace('.', ',') + ' %'; }
  function fmtPx(v) { return v == null ? '–' : Number(v).toLocaleString('es-ES', { maximumFractionDigits: 2 }); }

  function trades(root, list, opt = {}) {
    root.innerHTML = '';
    if (!list || !list.length) { root.appendChild(el('p', 'sla-note', 'No hay operaciones en esta ventana.')); return; }
    const rows = list.slice().sort((a, b) => (b.entry_date || '').localeCompare(a.entry_date || ''));
    const closed = rows.filter(t => !t.open), wins = closed.filter(t => t.return_pct > 0);
    const avg = closed.length ? closed.reduce((s, t) => s + t.return_pct, 0) / closed.length : null;
    root.appendChild(el('p', 'sla-note', closed.length + ' operaciones cerradas' + (closed.length ? ' · ' + Math.round(100 * wins.length / closed.length) + ' % ganadoras · media ' + fmtP(avg) : '') +
      ' · ' + (rows.length - closed.length) + ' abierta(s). ' + (opt.priceNote || 'Precios del cierre de la barra de señal, sin costes.')));
    const head = (opt.asset ? '<th>Activo</th>' : '') + '<th>Entrada</th><th class="n">Precio</th><th>Salida</th><th class="n">Precio</th><th class="n">Resultado</th>';
    const body = rows.map(t => '<tr>' + (opt.asset ? '<td>' + t.asset + '</td>' : '') + '<td>' + t.entry_date + '</td><td class="n">' + fmtPx(t.entry_price) +
      '</td><td>' + (t.open ? '<span class="sla-open">abierta</span>' : t.exit_date) + '</td><td class="n">' + fmtPx(t.exit_price) +
      '</td><td class="n ' + (t.return_pct >= 0 ? 'pos' : 'neg') + '">' + fmtP(t.return_pct) + '</td></tr>').join('');
    const wrap = el('div', 'sla-twrap', '<table class="sla-table"><thead><tr>' + head + '</tr></thead><tbody>' + body + '</tbody></table>');
    root.appendChild(wrap);
    const btn = el('button', 'sla-btn', 'Descargar CSV');
    btn.type = 'button';
    btn.onclick = () => {
      const cols = (opt.asset ? ['asset'] : []).concat(['entry_date', 'entry_price', 'exit_date', 'exit_price', 'return_pct', 'open']);
      const csv = [cols.join(',')].concat(rows.map(t => cols.map(c => t[c] == null ? '' : t[c]).join(','))).join('\n');
      const a = document.createElement('a');
      a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
      a.download = opt.filename || 'operaciones.csv'; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    };
    root.appendChild(btn);
  }

  // Convierte un array compacto [entrada, precio, salida, precio, %] en objetos
  function unpack(arr, asset) {
    return (arr || []).map(t => ({ asset, entry_date: t[0], entry_price: t[1], exit_date: t[2], exit_price: t[3], return_pct: t[4], open: t[2] == null }));
  }
  // Alinea una curva (fechas propias) a otras fechas, arrastrando el último valor
  function align(srcDates, srcVals, dates) {
    const out = []; let j = 0, last = null;
    for (const d of dates) { while (j < srcDates.length && srcDates[j] <= d) { last = srcVals[j]; j++; } out.push(last); }
    const first = out.find(v => v != null);
    return out.map(v => v == null ? first : v);
  }

  window.SLA = { panel, trades, unpack, align, rollingSharpe, drawdown };
})();
