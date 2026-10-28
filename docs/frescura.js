/* Sharpe Lab · sello de frescura "Actualizado hace X".
 * Lee la marca de tiempo que escriben los scripts en cada JSON (generated_at o
 * updated) y avisa si los datos van atrasados.
 *
 *   <p class="fresh" data-fresh-src="semis.json" data-fresh-max-h="36"></p>  -> automático
 *   SLFresh.mount(el, d.generated_at, 36)                                   -> desde un fetch propio
 */
(function () {
  const TZ = 'Europe/Madrid';
  function parse(s) {
    if (!s) return null;
    let t = String(s).trim();
    let m = t.match(/^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2})(?::\d{2}(?:\.\d+)?)?\s*(UTC|Z)?$/);
    if (m) return new Date(m[1] + 'T' + m[2] + ':00Z');            // "2026-10-28 00:31 UTC", "2026-10-28T00:31Z"
    const d = new Date(t);                                           // ISO con zona (+00:00)
    return isNaN(d) ? null : d;
  }
  function ago(ms) {
    const min = Math.round(ms / 60000);
    if (min < 1) return 'hace menos de 1 min';
    if (min < 60) return 'hace ' + min + ' min';
    const h = Math.round(min / 60);
    if (h < 48) return 'hace ' + h + ' h';
    return 'hace ' + Math.round(h / 24) + ' días';
  }
  function text(s, maxH) {
    const d = parse(s);
    if (!d) return { txt: 'Fecha de actualización desconocida', stale: true };
    const ms = Date.now() - d.getTime();
    const abs = d.toLocaleString('es-ES', { timeZone: TZ, day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
    const stale = maxH != null && ms > maxH * 3600e3;
    return { txt: 'Actualizado ' + ago(Math.max(ms, 0)) + ' · ' + abs + ' (hora de Madrid)' + (stale ? ' · ⚠ datos atrasados' : ''), stale, date: d };
  }
  function mount(el, s, maxH) {
    if (!el) return;
    const paint = () => { const r = text(s, maxH); el.textContent = r.txt; el.classList.toggle('stale', r.stale); if (r.date) el.title = r.date.toISOString(); };
    paint();
    clearInterval(el._fresh); el._fresh = setInterval(paint, 60000);
  }
  function auto() {
    document.querySelectorAll('[data-fresh-src]').forEach(el => {
      const maxH = el.dataset.freshMaxH ? +el.dataset.freshMaxH : 36;
      fetch(el.dataset.freshSrc, { cache: 'no-cache' }).then(r => r.json()).then(d => {
        const f = el.dataset.freshField;
        mount(el, f ? d[f] : (d.generated_at || d.updated), maxH);
      }).catch(() => { el.textContent = 'No se pudo leer la fecha de actualización'; });
    });
  }
  window.SLFresh = { parse, text, mount, auto };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', auto); else auto();
})();
