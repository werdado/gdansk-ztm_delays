/* Raport opóźnień: interfejs. Wszystkie teksty ze źródła wstawiane są przez textContent. */
(function () {
  'use strict';
  var A = window.ZtmAggregate;
  var COLORS = { green: '#2e9e48', orange: '#f08a1a', red: '#d32f2f', grey: '#9aa0a6' };
  var CAT = { green: 'bez opóźnienia', orange: 'do 5 min', red: 'ponad 5 min', grey: 'brak danych' };
  var PHASE = { pre_departure: 'przed odjazdem', en_route: 'w trasie', terminal_after_arrival: 'przy krańcu po dojeździe', unknown: 'nierozpoznana' };
  var FLAG = { ambiguous: 'niejednoznaczne dopasowanie', unmatched: 'poza trasą wariantu', no_delay: 'brak opóźnienia w rekordzie', conflict: 'konflikt wersji' };
  var SVGNS = 'http://www.w3.org/2000/svg';
  var $ = function (id) { return document.getElementById(id); };

  var S = { manifest: null, quality: null, geo: {}, summary: new Map(), st: null, map: null, layer: null, fitKey: null,
            worker: null, req: 0, courseCache: {}, showAll: false, canvas: null };

  /* ---------- pomocnicze ---------- */
  function h(tag, attrs) {
    var el = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      var v = attrs[k];
      if (v === null || v === undefined || v === false) return;
      if (k === 'class') el.className = v;
      else if (k.slice(0, 2) === 'on') el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? '' : v);
    });
    for (var i = 2; i < arguments.length; i++) add(el, arguments[i]);
    return el;
  }
  function add(el, c) {
    if (c === null || c === undefined || c === false) return;
    if (Array.isArray(c)) { c.forEach(function (x) { add(el, x); }); return; }
    el.appendChild(c.nodeType ? c : document.createTextNode(String(c)));
  }
  function sv(tag, attrs) {
    var el = document.createElementNS(SVGNS, tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      var v = attrs[k]; if (v === null || v === undefined) return;
      if (k.slice(0, 2) === 'on') el.addEventListener(k.slice(2), v); else el.setAttribute(k, v);
    });
    for (var i = 2; i < arguments.length; i++) add(el, arguments[i]);
    return el;
  }
  function clear(el) { while (el.firstChild) el.removeChild(el.firstChild); }
  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function fmtTime(L) { return new Date(L * 1000).toISOString().slice(0, 19).replace('T', ' '); }
  function fmtHM(L) { return new Date(L * 1000).toISOString().slice(11, 16); }
  function dayNum(date) { return Math.floor(Date.parse(date + 'T00:00:00Z') / 86400000); }
  function badge(v) { var c = A.classify(v); return h('span', { class: 'badge ' + c }, CAT[c]); }
  function status(msg, err) { var s = $('status'); if (!msg) { s.hidden = true; return; } s.hidden = false; s.className = 'notice' + (err ? ' error' : ''); s.textContent = msg; }
  function lineOf() { return S.manifest.lines.filter(function (l) { return l.name === S.st.line; })[0]; }
  function dirOf(line, id) { return line.directions.filter(function (d) { return d.id === id; })[0]; }

  /* ---------- stan w fragmencie adresu ---------- */
  function parseHash() {
    var p = new URLSearchParams(location.hash.replace(/^#/, ''));
    var num = function (k) { var v = p.get(k); return v === null || v === '' || isNaN(+v) ? null : +v; };
    return { line: p.get('line'), dir: num('dir'), variant: p.get('v') || '', days: p.has('days') ? p.get('days').split(',').filter(Boolean) : null,
             from: num('from'), to: num('to'), seg: num('seg'), course: num('course') };
  }
  function normalize(raw) {
    var m = S.manifest, st = {};
    var line = m.lines.filter(function (l) { return l.name === raw.line; })[0] || m.lines[0];
    st.line = line.name;
    var d = dirOf(line, raw.dir) || line.directions[0];
    st.dir = d.id;
    st.variant = d.variants.some(function (v) { return v.key === raw.variant; }) ? raw.variant : '';
    var all = m.range.days;
    var days = raw.days ? raw.days.filter(function (x) { return all.indexOf(x) >= 0; }) : null;
    st.days = days && days.length && days.length < all.length ? days : null;
    st.from = raw.from !== null && raw.from >= 0 && raw.from <= 23 ? Math.floor(raw.from) : 0;
    st.to = raw.to !== null && raw.to >= 0 && raw.to <= 24 ? Math.floor(raw.to) : 24;
    if (st.from === st.to) { st.from = 0; st.to = 24; }
    st.seg = raw.seg; st.course = raw.course;
    return st;
  }
  function serialize(st) {
    var p = new URLSearchParams();
    p.set('line', st.line); p.set('dir', st.dir);
    if (st.variant) p.set('v', st.variant);
    if (st.days) p.set('days', st.days.join(','));
    if (st.from !== 0 || st.to !== 24) { p.set('from', st.from); p.set('to', st.to); }
    if (st.seg !== null && st.seg !== undefined) p.set('seg', st.seg);
    if (st.course !== null && st.course !== undefined) p.set('course', st.course);
    return '#' + p.toString();
  }
  function go(patch, replace) {
    var st = Object.assign({}, S.st, patch);
    var hash = serialize(st);
    if (hash === location.hash) { applyHash(); return; }
    if (replace) history.replaceState(null, '', hash); else location.hash = hash;
    if (replace) applyHash();
  }
  function selection() {
    var m = S.manifest, st = S.st;
    var days = (st.days || m.range.days).map(dayNum);
    return { days: days, from: st.from * 3600, to: st.to * 3600 };
  }

  /* ---------- start ---------- */
  function fail(msg) { $('app').hidden = false; status(msg, true); }
  function boot() {
    if (location.protocol === 'file:') { $('file-notice').hidden = false; return; }
    $('app').hidden = false;
    status('Ładowanie danych…');
    ZtmFetch.json('data/manifest.json.gz').then(function (m) {
      if (m.format !== 1) throw new Error('nieobsługiwana wersja formatu danych: ' + m.format);
      if (!m.lines.length) throw new Error('raport nie zawiera żadnych linii');
      S.manifest = m;
      try { S.worker = new Worker('assets/worker.js'); S.worker.onmessage = onWorker; }
      catch (e) { fail('Nie udało się uruchomić przetwarzania w tle (Web Worker): ' + e.message); return; }
      $('period').textContent = 'Zakres: ' + m.range.from + ' – ' + m.range.to + ' (pełne doby czasu lokalnego Gdańska).';
      buildStaticFilters();
      renderQuality();
      ZtmFetch.json(m.quality).then(function (q) { S.quality = q; renderQuality(); }).catch(function () {});
      window.addEventListener('hashchange', applyHash);
      applyHash();
    }).catch(function (e) { fail('Nie udało się wczytać raportu: ' + e.message + '. Sprawdź, czy katalog jest udostępniony przez HTTP.'); });
  }

  var pending = {};
  function onWorker(ev) { var m = ev.data, p = pending[m.id]; if (!p) return; delete pending[m.id]; if (m.ok) p.res(m.result); else p.rej(new Error(m.error)); }
  function workerSummarize(line, st) {
    var id = ++S.req, sel = selection();
    var urls = Object.keys(line.days).sort().map(function (d) { return new URL(line.days[d], document.baseURI).href; });
    return new Promise(function (res, rej) {
      pending[id] = { res: res, rej: rej };
      S.worker.postMessage({ id: id, line: line.name, urls: urls, dir: st.dir, variant: st.variant || null, sel: { days: sel.days, from: sel.from, to: sel.to } });
    });
  }

  var token = 0;
  function applyHash() {
    var prevLine = S.st && S.st.line;
    S.st = normalize(parseHash());
    var canon = serialize(S.st);
    if (canon !== location.hash) history.replaceState(null, '', canon);
    syncFilters();
    var my = ++token, line = lineOf();
    var geoP = S.geo[line.name] ? Promise.resolve(S.geo[line.name]) :
      ZtmFetch.json(line.geometry).then(function (g) { S.geo[line.name] = g; return g; });
    var showCourse = S.st.course !== null;
    $('summary-view').hidden = showCourse; $('course-view').hidden = !showCourse;
    status('Przeliczanie…');
    Promise.all([geoP, workerSummarize(line, S.st)]).then(function (r) {
      if (my !== token) return;
      status('');
      S.summary = new Map(r[1]);
      if (showCourse) renderCourse(); else { renderSummary(); }
    }).catch(function (e) { if (my === token) status('Nie udało się wczytać danych linii ' + line.name + ': ' + e.message, true); });
  }

  /* ---------- filtry ---------- */
  function buildStaticFilters() {
    var m = S.manifest;
    var fl = $('f-line'); m.lines.forEach(function (l) { fl.appendChild(h('option', { value: l.name }, 'Linia ' + l.name)); });
    var ff = $('f-from'), ft = $('f-to');
    for (var i = 0; i <= 23; i++) ff.appendChild(h('option', { value: i }, i + ':00'));
    for (i = 0; i <= 24; i++) ft.appendChild(h('option', { value: i }, i + ':00'));
    var days = $('f-days');
    m.range.days.forEach(function (d) {
      days.appendChild(h('label', null, h('input', { type: 'checkbox', value: d, onchange: onDays }), d.slice(8) + '.' + d.slice(5, 7)));
    });
    fl.addEventListener('change', function () { go({ line: fl.value, dir: null, variant: '', seg: null, course: null }); });
    $('f-dir').addEventListener('change', function (e) { go({ dir: +e.target.value, variant: '', seg: null }); });
    $('f-variant').addEventListener('change', function (e) { go({ variant: e.target.value, seg: null }); });
    ff.addEventListener('change', onHours); ft.addEventListener('change', onHours);
    $('days-all').addEventListener('click', function () { go({ days: null }); });
  }
  function onDays() {
    var sel = Array.prototype.filter.call($('f-days').querySelectorAll('input'), function (i) { return i.checked; }).map(function (i) { return i.value; });
    if (!sel.length) { go({ days: null }); return; }
    go({ days: sel.length === S.manifest.range.days.length ? null : sel });
  }
  function onHours() { go({ from: +$('f-from').value, to: +$('f-to').value }); }
  function syncFilters() {
    var st = S.st, line = lineOf();
    $('f-line').value = st.line;
    var fd = $('f-dir'); clear(fd);
    line.directions.forEach(function (d) { fd.appendChild(h('option', { value: d.id }, 'Kierunek ' + d.id + ': do ' + d.label)); });
    fd.value = st.dir;
    var d = dirOf(line, st.dir), fv = $('f-variant'); clear(fv);
    fv.appendChild(h('option', { value: '' }, 'Wszystkie warianty'));
    d.variants.forEach(function (v) {
      fv.appendChild(h('option', { value: v.key }, v.key + ' → ' + v.headsign + (v.status === 'ok' ? '' : v.status === 'absent_in_gtfs' ? ' (brak w rozkładzie pomocniczym)' : ' (wyłączony: niejednoznaczny)')));
    });
    fv.value = st.variant;
    $('f-from').value = st.from; $('f-to').value = st.to;
    Array.prototype.forEach.call($('f-days').querySelectorAll('input'), function (i) { i.checked = !st.days || st.days.indexOf(i.value) >= 0; });
  }
  function filterText() {
    var st = S.st, m = S.manifest, line = lineOf(), d = dirOf(line, st.dir);
    var days = st.days ? st.days.map(function (x) { return x.slice(8) + '.' + x.slice(5, 7); }).join(', ') : 'wszystkie dni (' + m.range.from + ' – ' + m.range.to + ')';
    var hours = st.from === 0 && st.to === 24 ? 'cała doba' : st.from + ':00–' + st.to + ':00' + (st.from > st.to ? ' (przez północ)' : '');
    return 'Linia ' + st.line + ', kierunek do ' + d.label + (st.variant ? ', wariant ' + st.variant : ', wszystkie warianty') + '; dni: ' + days + '; pora: ' + hours + '.';
  }

  /* ---------- widok zbiorczy ---------- */
  function visibleSegments() {
    var geo = S.geo[S.st.line], st = S.st;
    var ids = null;
    if (st.variant) { var v = geo.variants.filter(function (x) { return x.key === st.variant; })[0]; ids = v ? new Set(v.segments) : new Set(); }
    return geo.segments.filter(function (s) { return s.dir === st.dir && (!ids || ids.has(s.id)); });
  }
  function segName(s) { return s.from.name + ' → ' + s.to.name; }

  function renderSummary() {
    var segs = visibleSegments(), st = S.st;
    var courseIds = new Set();
    S.summary.forEach(function (v) { v.courses.forEach(function (c) { courseIds.add(c.id); }); });
    var withData = segs.filter(function (s) { return S.summary.has(s.id); }).length;
    $('active-filter').textContent = filterText() + ' Kursów z danymi: ' + courseIds.size + '; odcinków z danymi: ' + withData + ' z ' + segs.length + '.';
    var note = $('midnight-note');
    var lastDay = dayNum(S.manifest.range.to), sel = { days: new Set(selection().days), from: selection().from, to: selection().to };
    if (A.crossesPastLastDay(sel, lastDay)) { note.hidden = false; note.textContent = 'Zakres przez północ dotyczy też nocy po ostatnim przetworzonym dniu (' + S.manifest.range.to + '); obserwacje po tej dobie nie są dostępne, więc wynik tej nocy jest niepełny.'; }
    else note.hidden = true;
    var noVariantData = st.variant && !segs.length;
    renderMap(segs);
    renderCharts(noVariantData);
    renderDetails();
  }
  function segColor(id) { var s = S.summary.get(id); return COLORS[A.classify(s ? s.level.median : null)]; }
  function segText(id) { var s = S.summary.get(id); if (!s) return 'brak danych'; return 'mediana ' + A.formatDelay(s.level.median) + ', kursów: ' + s.level.n; }

  function ensureMap() {
    if (S.map) return;
    S.canvas = L.canvas({ padding: 0.5 });
    S.map = L.map('map', { preferCanvas: true, renderer: S.canvas, zoomSnap: 0.25 }).setView([54.37, 18.6], 12);
    var tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">współtwórcy OpenStreetMap</a>' });
    tiles.on('tileerror', function () { $('tile-note').hidden = false; });
    tiles.addTo(S.map);
    S.layer = L.layerGroup().addTo(S.map);
  }
  function renderMap(segs) {
    ensureMap();
    S.map.invalidateSize();
    S.layer.clearLayers();
    var bounds = [];
    segs.forEach(function (s) {
      var sel = S.st.seg === s.id;
      var base = L.polyline(s.path, { color: sel ? '#000' : '#fff', weight: sel ? 10 : 7, opacity: 0.9, renderer: S.canvas, interactive: false });
      var line = L.polyline(s.path, { color: segColor(s.id), weight: 5, opacity: 1, renderer: S.canvas, dashArray: S.summary.has(s.id) ? null : '4 6' });
      line.bindTooltip(h('span', null, segName(s) + ' — ' + segText(s.id)), { sticky: true });
      line.on('click', function () { go({ seg: s.id }); });
      S.layer.addLayer(base); S.layer.addLayer(line);
      s.path.forEach(function (p) { bounds.push(p); });
    });
    var key = S.st.line + '|' + S.st.dir + '|' + S.st.variant;
    if (bounds.length && key !== S.fitKey) { S.map.fitBounds(bounds, { padding: [20, 20] }); S.fitKey = key; }
  }

  function renderCharts(noData) {
    var root = $('charts'); clear(root);
    var geo = S.geo[S.st.line], line = lineOf(), d = dirOf(line, S.st.dir);
    var segById = {}; geo.segments.forEach(function (s) { segById[s.id] = s; });
    var variants = geo.variants.filter(function (v) { return v.dir === S.st.dir && (!S.st.variant || v.key === S.st.variant); });
    variants.forEach(function (v) { root.appendChild(variantChart(v, segById)); });
    var skipped = d.variants.filter(function (v) { return v.status !== 'ok' && (!S.st.variant || v.key === S.st.variant); });
    skipped.forEach(function (v) {
      root.appendChild(h('p', { class: 'notice' }, 'Wariant ' + v.key + ' (do ' + v.headsign + '): ' + (v.status === 'absent_in_gtfs' ? 'nieobecny w pomocniczym rozkładzie — brak geometrii i wartości odcinków; kursy (' + v.courses + ') są dostępne wyłącznie jako obserwacje.' : 'niejednoznaczny w rozkładzie pomocniczym — wyłączony z wyników.')));
    });
    if (!variants.length && !skipped.length) root.appendChild(h('p', { class: 'muted' }, 'Brak wariantów do pokazania.'));
  }

  function niceStep(range) { var steps = [60, 120, 300, 600, 900, 1800, 3600]; for (var i = 0; i < steps.length; i++) if (range / steps[i] <= 6) return steps[i]; return 3600; }

  function variantChart(v, segById) {
    var W = 720, Ht = 260, ml = 52, mr = 12, mt = 14, mb = 40;
    var wrap = h('div', { class: 'chart-wrap' });
    var segs = v.segments.map(function (id) { return segById[id]; });
    var total = segs.reduce(function (a, s) { return a + s.length_m; }, 0) || 1;
    var vals = [0, 300];
    segs.forEach(function (s) { var r = S.summary.get(s.id); if (r) { vals.push(r.level.median, r.level.max); } });
    var lo = Math.min.apply(null, vals), hi = Math.max.apply(null, vals), span = Math.max(hi - lo, 120);
    lo = lo < 0 ? lo - span * 0.05 : 0; hi = hi + span * 0.08;
    var X = function (m) { return ml + (m / total) * (W - ml - mr); }, Y = function (val) { return mt + (hi - val) / (hi - lo) * (Ht - mt - mb); };
    var svg = sv('svg', { viewBox: '0 0 ' + W + ' ' + Ht, role: 'img', 'aria-label': 'Wykres opóźnienia wzdłuż wariantu ' + v.key });
    var step = niceStep(hi - lo);
    for (var t = Math.ceil(lo / step) * step; t <= hi; t += step) {
      svg.appendChild(sv('line', { x1: ml, x2: W - mr, y1: Y(t), y2: Y(t), class: 'grid-line' }));
      svg.appendChild(sv('text', { x: ml - 5, y: Y(t) + 4, 'text-anchor': 'end' }, t / 60 + ' min'));
    }
    svg.appendChild(sv('line', { x1: ml, x2: W - mr, y1: Y(300), y2: Y(300), stroke: COLORS.red, 'stroke-dasharray': '5 4' }));
    svg.appendChild(sv('text', { x: W - mr, y: Y(300) - 3, 'text-anchor': 'end' }, 'próg 5 min'));
    var cum = 0;
    segs.forEach(function (s) {
      var x0 = X(cum), x1 = X(cum + s.length_m), w = Math.max(x1 - x0 - 1, 1);
      var r = S.summary.get(s.id), sel = S.st.seg === s.id;
      var label = segName(s) + ': ' + (r ? 'mediana ' + A.formatDelay(r.level.median) + ' (' + CAT[A.classify(r.level.median)] + '), największe ' + A.formatDelay(r.level.max) + ', kursów ' + r.level.n : 'brak danych');
      var g = sv('g', { class: 'bar-g', tabindex: 0, role: 'button', 'aria-label': label, onclick: function () { go({ seg: s.id }); }, onkeydown: function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go({ seg: s.id }); } } });
      g.appendChild(sv('title', null, label));
      g.appendChild(sv('rect', { x: x0, y: Y(hi), width: w, height: Y(lo) - Y(hi), fill: 'transparent', style: 'pointer-events:all;cursor:pointer' }));
      if (!r) {
        g.appendChild(sv('rect', { x: x0, y: Y(hi), width: w, height: Y(lo) - Y(hi), class: 'nodata' + (sel ? ' sel' : '') }));
      } else {
        var y = Y(r.level.median), y0 = Y(0);
        g.appendChild(sv('rect', { x: x0, y: Math.min(y, y0), width: w, height: Math.max(Math.abs(y0 - y), 2), fill: COLORS[A.classify(r.level.median)], opacity: 0.85, class: 'bar' + (sel ? ' sel' : '') }));
        var ym = Y(r.level.max);
        g.appendChild(sv('path', { d: 'M' + (x0 + w / 2) + ' ' + (ym - 5) + ' l4 8 h-8 z', fill: '#222' }));
      }
      svg.appendChild(g);
      cum += s.length_m;
    });
    svg.appendChild(sv('line', { x1: ml, x2: W - mr, y1: Y(0), y2: Y(0), class: 'axis' }));
    for (var km = 0; km * 1000 <= total; km += total > 8000 ? 2 : 1) {
      svg.appendChild(sv('text', { x: X(km * 1000), y: Ht - 22, 'text-anchor': 'middle' }, km + ' km'));
    }
    svg.appendChild(sv('text', { x: ml, y: Ht - 6, 'text-anchor': 'start' }, segs.length ? segs[0].from.name : ''));
    svg.appendChild(sv('text', { x: W - mr, y: Ht - 6, 'text-anchor': 'end' }, segs.length ? segs[segs.length - 1].to.name : ''));
    wrap.appendChild(h('h3', null, 'Wariant ' + v.key + ' → ' + v.headsign));
    wrap.appendChild(svg);
    wrap.appendChild(h('p', { class: 'muted small' }, 'Słupki: mediana opóźnienia przy końcu odcinka (poniżej zera — przed czasem); ▲ — największe opóźnienie. Jasny prostokąt: brak danych.'));
    var rows = segs.map(function (s) {
      var r = S.summary.get(s.id);
      return h('tr', null, h('td', null, segName(s)), h('td', null, r ? A.formatDelay(r.level.median) : 'brak danych'), h('td', null, badge(r ? r.level.median : null)),
        h('td', null, r ? A.formatDelay(r.level.max) : '—'), h('td', null, r ? r.level.n : 0), h('td', null, r ? r.change.n : 0));
    });
    wrap.appendChild(h('details', null, h('summary', null, 'Tabela odcinków wariantu ' + v.key),
      h('div', { class: 'table-wrap' }, h('table', null, h('thead', null, h('tr', null, ['Odcinek', 'Typowe opóźnienie', 'Kategoria', 'Największe', 'Kursów (poziom)', 'Kursów (zmiana)'].map(function (x) { return h('th', null, x); }))), h('tbody', null, rows)))));
    return wrap;
  }

  function renderDetails() {
    var root = $('details'); clear(root);
    var geo = S.geo[S.st.line], seg = geo.segments.filter(function (s) { return s.id === S.st.seg; })[0];
    root.appendChild(h('h2', null, 'Szczegóły odcinka'));
    if (!seg) { root.appendChild(h('p', { class: 'muted' }, 'Wybierz odcinek na mapie lub wykresie.')); return; }
    var r = S.summary.get(seg.id);
    root.appendChild(h('p', null, h('strong', null, segName(seg)), ' (' + Math.round(seg.length_m) + ' m)'));
    if (!r) { root.appendChild(h('p', null, h('span', { class: 'badge grey' }, 'brak danych'), ' Brak kwalifikujących się wartości dla tego odcinka i wybranego filtra.')); return; }
    root.appendChild(h('dl', { class: 'kv' },
      h('dt', null, 'Typowe opóźnienie (mediana)'), h('dd', null, A.formatDelay(r.level.median), ' ', badge(r.level.median)),
      h('dt', null, 'Największe opóźnienie'), h('dd', null, A.formatDelay(r.level.max)),
      h('dt', null, 'Kursów z wartością przy końcu odcinka'), h('dd', null, String(r.level.n)),
      h('dt', null, 'Typowa zmiana na odcinku (mediana)'), h('dd', null, A.formatChange(r.change.median)),
      h('dt', null, 'Kursów, dla których znana jest zmiana'), h('dd', null, r.change.n + (r.change.n < r.level.n ? ' (mniej niż kursów z poziomem: dla części brak początku odcinka lub początek poza filtrem czasu)' : '')),
    ));
    var list = S.showAll ? r.courses : r.courses.slice(0, 100);
    var rows = list.map(function (c) {
      return h('tr', null, h('td', null, fmtTime(c.endL)), h('td', null, fmtHM(c.courseStartL)), h('td', null, c.vehicle),
        h('td', null, A.formatDelay(c.end), ' ', badge(c.end)), h('td', null, c.change === null ? 'nieznana' : A.formatChange(c.change)),
        h('td', null, c.dist === null || c.dist === undefined ? '—' : Math.round(c.dist) + ' m'),
        h('td', null, h('button', { type: 'button', onclick: function () { go({ course: c.id }); } }, 'Pokaż kurs')));
    });
    root.appendChild(h('h3', null, 'Kursy będące podstawą wyniku (' + r.courses.length + ')'));
    root.appendChild(h('div', { class: 'table-wrap' }, h('table', null,
      h('thead', null, h('tr', null, ['Koniec odcinka (czas lokalny)', 'Start kursu', 'Pojazd', 'Opóźnienie przy końcu', 'Zmiana', 'Odległość od przystanku', ''].map(function (x) { return h('th', null, x); }))),
      h('tbody', null, rows))));
    if (r.courses.length > 100 && !S.showAll) root.appendChild(h('button', { type: 'button', onclick: function () { S.showAll = true; renderDetails(); } }, 'Pokaż wszystkie ' + r.courses.length + ' kursów'));
  }

  /* ---------- widok kursu ---------- */
  function courseUrl(line, id) { return new URL(line.geometry.replace(/geometry\.json\.gz$/, 'courses/' + id + '.json.gz'), document.baseURI).href; }
  function renderCourse() {
    var root = $('course-view'); clear(root);
    var line = lineOf(), id = S.st.course;
    var back = h('button', { type: 'button', class: 'primary', onclick: function () { go({ course: null }); } }, '← Wróć do podsumowania');
    root.appendChild(h('div', { class: 'toolbar' }, back, h('span', { class: 'muted' }, 'Filtry zostają zachowane: ' + filterText())));
    var body = h('div', { class: 'card' }, h('p', null, 'Ładowanie kursu ' + id + '…'));
    root.appendChild(body);
    var cached = S.courseCache[line.name + '/' + id];
    var p = cached ? Promise.resolve(cached) : ZtmFetch.json(courseUrl(line, id));
    var my = token;
    p.then(function (c) { S.courseCache[line.name + '/' + id] = c; if (my !== token) return; clear(body); body.className = ''; body.appendChild(courseBody(c)); window.scrollTo(0, 0); })
     .catch(function (e) {
       if (my !== token) return;
       clear(body);
       body.appendChild(h('div', { class: 'notice error' }, 'Nie udało się pobrać danych kursu ' + id + ' (' + e.message + '). '));
       body.appendChild(h('button', { type: 'button', onclick: function () { renderCourse(); } }, 'Spróbuj ponownie'));
     });
  }

  function courseBody(c) {
    var geo = S.geo[S.st.line], segById = {};
    geo.segments.forEach(function (s) { segById[s.id] = s; });
    var v = geo.variants.filter(function (x) { return x.key === c.variant; })[0];
    var out = h('div', null);
    out.appendChild(h('div', { class: 'card' },
      h('h2', null, 'Kurs linii ' + c.line + ', do ' + c.headsign),
      h('p', { class: 'notice' }, 'Pełny kurs: widok pokazuje cały dostępny przebieg, także poza wybranym filtrem czasu.'),
      c.truncated ? h('p', { class: 'notice' }, 'Kurs obcięty granicą przetwarzanego zakresu (' + ({ start: 'brak początku', end: 'brak końca', both: 'brak początku i końca' }[c.truncated] || c.truncated) + ') — widoczny jest tylko jego fragment.') : null,
      c.variant_status !== 'ok' ? h('p', { class: 'notice' }, 'Wariant ' + c.variant + ' jest nieobecny lub wyłączony w pomocniczym rozkładzie: pokazujemy obserwacje, ale bez odcinków i wartości przy końcu odcinków.') : null,
      h('dl', { class: 'kv' },
        h('dt', null, 'Rozkładowy start'), h('dd', null, fmtTime(c.startL)),
        h('dt', null, 'Wariant'), h('dd', null, c.variant), h('dt', null, 'Pojazd'), h('dd', null, c.vehicle), h('dt', null, 'Zadanie przewozowe'), h('dd', null, c.service),
        h('dt', null, 'Obserwacji'), h('dd', null, String(c.observations.length))),
      arrivalBox(c)));
    out.appendChild(h('div', { class: 'card' }, h('h2', null, 'Opóźnienie w trakcie kursu'), courseChart(c, v, segById)));
    out.appendChild(segmentsTable(c, segById));
    out.appendChild(observationsTable(c));
    out.appendChild(sourcesList(c));
    return out;
  }
  function arrivalBox(c) {
    if (c.arrival === null || c.arrival === undefined) return null;
    if (c.arrival.uncertain) return h('p', { class: 'notice' }, 'Dojazd do krańca: niepewny — ' + c.arrival.uncertain);
    return h('p', null, h('strong', null, 'Dojazd do krańca: '), A.formatDelay(c.arrival.delay), ' ', badge(c.arrival.delay), ' (ostatnia obserwacja w ruchu przed postojem; późniejsze obserwacje przy krańcu pokazano osobno).');
  }

  function courseChart(c, v, segById) {
    var obs = c.observations;
    var pre = [], main = [], post = [];
    obs.forEach(function (o, i) { o._i = i; (o.phase === 'pre_departure' ? pre : o.phase === 'terminal_after_arrival' ? post : main).push(o); });
    var W = 760, Ht = 270, ml = 52, mr = 12, mt = 14, mb = 36;
    var bandPre = pre.length ? 90 : 0, bandPost = post.length ? 110 : 0, gap = 14;
    var x0 = ml + (bandPre ? bandPre + gap : 0), x1 = W - mr - (bandPost ? bandPost + gap : 0);
    var vals = [0, 300]; obs.forEach(function (o) { if (o.delay !== null && o.delay !== undefined) vals.push(o.delay); });
    var lo = Math.min.apply(null, vals), hi = Math.max.apply(null, vals), sp = Math.max(hi - lo, 120);
    lo = lo < 0 ? lo - sp * 0.05 : 0; hi += sp * 0.08;
    var Y = function (val) { return mt + (hi - val) / (hi - lo) * (Ht - mt - mb); };
    var svg = sv('svg', { viewBox: '0 0 ' + W + ' ' + Ht, role: 'img', 'aria-label': 'Opóźnienie obserwacji kursu' });
    var step = niceStep(hi - lo);
    for (var t = Math.ceil(lo / step) * step; t <= hi; t += step) {
      svg.appendChild(sv('line', { x1: ml, x2: W - mr, y1: Y(t), y2: Y(t), class: 'grid-line' }));
      svg.appendChild(sv('text', { x: ml - 5, y: Y(t) + 4, 'text-anchor': 'end' }, t / 60 + ' min'));
    }
    svg.appendChild(sv('line', { x1: ml, x2: W - mr, y1: Y(300), y2: Y(300), stroke: COLORS.red, 'stroke-dasharray': '5 4' }));
    svg.appendChild(sv('line', { x1: ml, x2: W - mr, y1: Y(0), y2: Y(0), class: 'axis' }));
    var dot = function (o, x, r) {
      if (o.delay === null || o.delay === undefined) return;
      var el = sv('circle', { cx: x, cy: Y(o.delay), r: r || 3, fill: COLORS[A.classify(o.delay)], stroke: '#333', 'stroke-width': 0.6 }, sv('title', null, fmtTime(o.tL) + ': ' + A.formatDelay(o.delay)));
      svg.appendChild(el);
    };
    // przedział główny
    var hasSegs = v && v.segments.length && c.variant_status === 'ok';
    var total = hasSegs ? v.segments.reduce(function (a, id) { return a + segById[id].length_m; }, 0) : 1;
    var X;
    if (hasSegs) {
      X = function (s) { return x0 + (s / total) * (x1 - x0); };
      var cum = 0, byseg = {}; c.segments.forEach(function (s) { byseg[s.seg] = s; });
      v.segments.forEach(function (id) {
        var sg = segById[id], a = X(cum), b = X(cum + sg.length_m), cs = byseg[id];
        var missing = !cs || !cs.end;
        if (missing) svg.appendChild(sv('rect', { x: a, y: mt, width: Math.max(b - a - 1, 1), height: Ht - mt - mb, class: 'nodata' }, sv('title', null, segName(sg) + ': brak wartości' + (cs && cs.note ? ' — ' + cs.note : ''))));
        else svg.appendChild(sv('line', { x1: b, x2: b, y1: mt, y2: Ht - mb, class: 'grid-line' }));
        cum += sg.length_m;
      });
      svg.appendChild(sv('text', { x: x0, y: Ht - 20, 'text-anchor': 'start' }, segById[v.segments[0]].from.name));
      svg.appendChild(sv('text', { x: x1, y: Ht - 20, 'text-anchor': 'end' }, segById[v.segments[v.segments.length - 1]].to.name));
      svg.appendChild(sv('text', { x: (x0 + x1) / 2, y: Ht - 6, 'text-anchor': 'middle' }, 'trasa; jasne pola: odcinki bez wartości'));
      var pts = main.filter(function (o) { return o.s !== null && o.s !== undefined && o.delay !== null && o.delay !== undefined; });
      svg.appendChild(sv('polyline', { points: pts.map(function (o) { return X(o.s) + ',' + Y(o.delay); }).join(' '), fill: 'none', stroke: '#456', 'stroke-width': 1.2 }));
      pts.forEach(function (o) { dot(o, X(o.s), 2.6); });
      c.segments.forEach(function (s) { if (s.end) { var o = obs[s.end.obs]; if (o && o.s !== null) svg.appendChild(sv('circle', { cx: X(o.s), cy: Y(o.delay), r: 5.5, fill: 'none', stroke: '#000', 'stroke-width': 1.5 }, sv('title', null, 'Wartość przy końcu odcinka ' + segName(segById[s.seg]) + ': ' + A.formatDelay(o.delay)))); } });
    } else {
      X = function (i) { return x0 + (i / Math.max(main.length - 1, 1)) * (x1 - x0); };
      svg.appendChild(sv('text', { x: (x0 + x1) / 2, y: Ht - 6, 'text-anchor': 'middle' }, 'kolejne obserwacje (bez geometrii trasy)'));
      main.forEach(function (o, i) { dot(o, X(i), 2.6); });
    }
    var bandDots = function (list, bx, bw, label) {
      svg.appendChild(sv('rect', { x: bx, y: mt, width: bw, height: Ht - mt - mb, fill: '#f3f0fa', stroke: '#c9c1e0' }));
      svg.appendChild(sv('text', { x: bx + bw / 2, y: Ht - 20, 'text-anchor': 'middle' }, label));
      list.forEach(function (o, i) { dot(o, bx + 8 + (i + 0.5) * ((bw - 16) / list.length), 3.2); });
    };
    if (pre.length) bandDots(pre, ml, bandPre, 'przed odjazdem');
    if (post.length) bandDots(post, W - mr - bandPost, bandPost, 'przy krańcu po dojeździe');
    var wrap = h('div', { class: 'chart-wrap' }, svg,
      h('p', { class: 'muted small' }, 'Kropki: obserwacje (kolor = kategoria opóźnienia); czarne obwódki: wartości przy końcu odcinków. Fioletowe pola: obserwacje przed odjazdem i przy krańcu po dojeździe — nie są wartościami początku ani dojazdu.'));
    return wrap;
  }

  function segmentsTable(c, segById) {
    var rows = c.segments.map(function (s) {
      var sg = segById[s.seg];
      return h('tr', null, h('td', null, sg ? segName(sg) : '#' + s.seg),
        h('td', null, s.end ? [A.formatDelay(s.end.delay), ' ', badge(s.end.delay), h('br'), h('span', { class: 'muted small' }, 'obserwacja ' + Math.round(s.end.dist_m) + ' m przed przystankiem, następna po ' + s.end.gap_s + ' s')] : h('span', { class: 'badge grey' }, 'brak danych')),
        h('td', null, s.start ? A.formatDelay(s.start.delay) + (s.start.kind === 'course_start' ? ' (początek kursu)' : ' (koniec poprzedniego odcinka)') : 'nieznany'),
        h('td', null, s.change === null || s.change === undefined ? 'nieznana' : A.formatChange(s.change)), h('td', null, s.note || ''));
    });
    return h('div', { class: 'card' }, h('h2', null, 'Odcinki kursu'),
      c.segments.length ? h('div', { class: 'table-wrap' }, h('table', null, h('thead', null, h('tr', null, ['Odcinek', 'Opóźnienie przy końcu', 'Początek odcinka', 'Zmiana', 'Uwagi'].map(function (x) { return h('th', null, x); }))), h('tbody', null, rows))) : h('p', { class: 'muted' }, 'Brak odcinków dla tego kursu.'));
  }
  function observationsTable(c) {
    var rows = c.observations.map(function (o, i) {
      return h('tr', null, h('td', null, String(i)), h('td', null, fmtTime(o.tL)), h('td', null, o.delay === null || o.delay === undefined ? 'brak' : A.formatDelay(o.delay)),
        h('td', null, o.speed === null || o.speed === undefined ? '—' : o.speed + ' km/h'), h('td', null, PHASE[o.phase] || o.phase),
        h('td', null, (o.flags || []).map(function (f) { return FLAG[f] || f; }).join(', ')), h('td', null, (o.src || []).map(function (x) { return '#' + x; }).join(', ')));
    });
    return h('div', { class: 'card' }, h('details', null, h('summary', null, 'Wszystkie obserwacje kursu (' + c.observations.length + ')'),
      h('div', { class: 'table-wrap' }, h('table', null, h('thead', null, h('tr', null, ['Nr', 'Czas lokalny', 'Opóźnienie', 'Prędkość', 'Faza', 'Uwagi', 'Zapisy'].map(function (x) { return h('th', null, x); }))), h('tbody', null, rows)))));
  }
  function sourcesList(c) {
    var items = c.sources.map(function (s, i) {
      return h('li', null, h('strong', null, '#' + i + ' '), s.snapshot || '(brak zapisu)', h('br'),
        h('span', { class: 'muted small' }, 'manifest: ' + (s.manifest || 'brak (luka pochodzenia)') + '; przebieg: ' + (s.run_status || '—') + ', źródło: ' + (s.source_status || '—') + '; pobrano: ' + (s.fetchedAt || '—') + (s.provenance_gap ? '; LUKA POCHODZENIA' : '')));
    });
    return h('div', { class: 'card' }, h('details', null, h('summary', null, 'Zapisy źródłowe i manifesty (' + c.sources.length + ')'), h('ol', { start: 0 }, items)));
  }

  /* ---------- jakość ---------- */
  var LABELS = { inputs: 'Wejścia', range: 'Zakres', counts: 'Liczniki', lines: 'Linie', notes: 'Uwagi', archive: 'Archiwum', gtfs: 'Pomocniczy GTFS', gtfs_feed_end_date: 'Koniec kalendarza GTFS',
    from: 'Od', to: 'Do', skipped_days: 'Pominięte doby', reason: 'Powód', date: 'Data', source_records: 'Zapisów źródłowych', snapshots_read: 'Odczytanych zapisów', snapshot_errors: 'Błędów odczytu zapisów',
    provenance_gaps: 'Luk pochodzenia (brak manifestu)', raw_records: 'Rekordów surowych', observations: 'Obserwacji po deduplikacji', conflicts: 'Konfliktów wersji', without_trip: 'Bez identyfikacji kursu',
    skipped_records: 'Pominiętych rekordów (bez kursu)', raw_skipped_records: 'Pominiętych rekordów surowych', courses: 'Kursów', variants_absent_in_gtfs: 'Warianty nieobecne w rozkładzie', segment_coverage: 'Pokrycie odcinków',
    passes: 'Przejazdów', with_value: 'z wartością', with_change: 'ze zmianą', variant: 'Wariant' };
  function renderValue(v) {
    if (v === null || v === undefined) return document.createTextNode('—');
    if (Array.isArray(v)) { if (v.every(function (x) { return typeof x !== 'object' || x === null; })) return h('ul', null, v.map(function (x) { return h('li', null, String(x)); })); return h('ul', null, v.map(function (x) { return h('li', null, renderValue(x)); })); }
    if (typeof v === 'object') { var dl = h('dl', { class: 'kv' }); Object.keys(v).forEach(function (k) { dl.appendChild(h('dt', null, LABELS[k] || k)); dl.appendChild(h('dd', null, renderValue(v[k]))); }); return dl; }
    return document.createTextNode(String(v));
  }
  function renderQuality() {
    var root = $('quality'); clear(root);
    var m = S.manifest; if (!m) return;
    root.appendChild(h('h3', null, 'Raport'));
    root.appendChild(renderValue({ 'Wygenerowano': m.generated, 'Wersja reguł': m.rules_version, 'Zakres': m.range.from + ' – ' + m.range.to, 'Pominięte doby': (m.range.skipped_days || []).map(function (d) { return typeof d === 'string' ? d : d.date; }), 'Parametry': m.params }));
    if (S.quality) { root.appendChild(h('h3', null, 'Jakość danych i pochodzenie')); root.appendChild(renderValue(S.quality)); }
    else root.appendChild(h('p', { class: 'muted' }, 'Ładowanie podsumowania jakości…'));
  }

  boot();
})();
