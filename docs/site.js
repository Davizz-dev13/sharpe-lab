/* Sharpe Lab · barra de navegación común: menú compacto en el móvil y desplegables en el ordenador. */
(function () {
  var root = document.documentElement;
  root.classList.add('js');
  function wrapTables() {
    document.querySelectorAll('main table').forEach(function (t) {
      var p = t.parentElement;
      if (!p || p.classList.contains('tscroll') || p.classList.contains('twrap') || p.classList.contains('sla-twrap')) return;
      var w = document.createElement('div'); w.className = 'tscroll'; p.insertBefore(w, t); w.appendChild(t);
    });
  }
  function init() {
    wrapTables();
    var nav = document.querySelector('nav.topnav');
    if (!nav) return;
    var toggle = nav.querySelector('.nav-toggle');
    var groups = [].slice.call(nav.querySelectorAll('.nav-group'));
    function closeGroups(except) {
      groups.forEach(function (g) {
        if (g !== except) { g.classList.remove('open'); var b = g.querySelector('.nav-gbtn'); if (b) b.setAttribute('aria-expanded', 'false'); }
      });
    }
    function setMenu(open) {
      nav.classList.toggle('menu-open', open);
      if (toggle) toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    }
    if (toggle) toggle.addEventListener('click', function () { setMenu(!nav.classList.contains('menu-open')); });
    groups.forEach(function (g) {
      var b = g.querySelector('.nav-gbtn');
      if (!b) return;
      b.addEventListener('click', function (e) {
        e.stopPropagation();
        var open = !g.classList.contains('open');
        closeGroups(g);
        g.classList.toggle('open', open);
        b.setAttribute('aria-expanded', open ? 'true' : 'false');
      });
    });
    document.addEventListener('click', function (e) { if (!nav.contains(e.target)) { closeGroups(); setMenu(false); } });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') { closeGroups(); setMenu(false); } });
    nav.querySelectorAll('a').forEach(function (a) { a.addEventListener('click', function () { closeGroups(); setMenu(false); }); });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
