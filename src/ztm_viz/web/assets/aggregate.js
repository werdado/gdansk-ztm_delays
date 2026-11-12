/* Statystyki raportu: czysty moduł bez zależności (Worker: importScripts, Node: require). */
(function (root) {
  'use strict';
  var DAY = 86400;

  function median(values) {
    var a = values.filter(function (v) { return v !== null && v !== undefined; }).sort(function (x, y) { return x - y; });
    var n = a.length;
    if (!n) return null;
    return n % 2 ? a[(n - 1) / 2] : (a[n / 2 - 1] + a[n / 2]) / 2;
  }

  // Klasyfikacja wartości przed zaokrągleniem: <=0 zielony, (0,300] pomarańczowy, >300 czerwony.
  function classify(v) {
    if (v === null || v === undefined || isNaN(v)) return 'grey';
    if (v <= 0) return 'green';
    if (v <= 300) return 'orange';
    return 'red';
  }

  function formatDuration(sec) {
    var s = Math.round(Math.abs(sec));
    var m = Math.floor(s / 60), r = s % 60;
    if (m === 0) return r + ' s';
    return m + ' min' + (r ? ' ' + r + ' s' : '');
  }

  function formatDelay(v) {
    if (v === null || v === undefined || isNaN(v)) return 'brak danych';
    if (v < 0 && Math.round(v) !== 0) return formatDuration(v) + ' przed czasem';
    if (Math.round(v) === 0) return '0 s';
    return formatDuration(v) + ' opóźnienia';
  }

  function formatChange(v) {
    if (v === null || v === undefined || isNaN(v)) return 'brak danych';
    var r = Math.round(v);
    if (r === 0) return 'bez zmiany (0 s)';
    return (r > 0 ? '+' : '−') + formatDuration(r) + (r > 0 ? ' (wzrost)' : ' (spadek)');
  }

  // sel = {days: Set<numer lokalnej doby> | null (wszystkie), from, to: sekundy doby}
  function inSelection(L, sel) {
    var day = Math.floor(L / DAY), tod = L - day * DAY;
    var from = sel.from, to = sel.to;
    var daysOk = function (d) { return !sel.days || sel.days.has(d); };
    if (from === to || (from === 0 && to >= DAY)) return daysOk(day);
    if (from < to) return daysOk(day) && tod >= from && tod < to;
    return (daysOk(day) && tod >= from) || (daysOk(day - 1) && tod < to);
  }

  // Czy zakres przez północ zaznaczonego ostatniego przetworzonego dnia wychodzi poza zakres.
  function crossesPastLastDay(sel, lastDay) {
    if (!(sel.from > sel.to)) return false;
    return !!sel.days && sel.days.has(lastDay);
  }

  function stats(vals) {
    return { n: vals.length, median: median(vals), max: vals.length ? Math.max.apply(null, vals) : null };
  }

  // days: pakiety dobowe (FORMAT.md). opts: {sel, dir, variant}. Zwraca Map(segId -> podsumowanie).
  function summarize(days, opts) {
    var sel = opts.sel;
    var best = new Map(); // "kurs|odcinek" -> wkład (jeden na kurs i odcinek)
    days.forEach(function (d) {
      var c = d.c;
      for (var i = 0; i < c.seg.length; i++) {
        var crs = d.courses[c.course[i]];
        if (opts.dir !== undefined && opts.dir !== null && crs.dir !== opts.dir) continue;
        if (opts.variant && crs.variant !== opts.variant) continue;
        var key = crs.id + '|' + c.seg[i];
        var prev = best.get(key);
        if (prev && prev.endL <= c.endL[i]) continue;
        best.set(key, { id: crs.id, seg: c.seg[i], endL: c.endL[i], end: c.end[i], startL: c.startL[i], start: c.start[i], dist: c.dist ? c.dist[i] : null, variant: crs.variant, vehicle: crs.vehicle, courseStartL: crs.startL });
      }
    });
    var perSeg = new Map();
    best.forEach(function (r) {
      if (!inSelection(r.endL, sel)) return;
      var s = perSeg.get(r.seg);
      if (!s) { s = { levels: [], changes: [], courses: [] }; perSeg.set(r.seg, s); }
      var change = null;
      if (r.start !== null && r.start !== undefined && r.startL !== null && r.startL !== undefined && inSelection(r.startL, sel)) {
        change = r.end - r.start;
      }
      s.levels.push(r.end);
      if (change !== null) s.changes.push(change);
      s.courses.push({ id: r.id, end: r.end, change: change, endL: r.endL, dist: r.dist, variant: r.variant, vehicle: r.vehicle, courseStartL: r.courseStartL });
    });
    var out = new Map();
    perSeg.forEach(function (s, seg) {
      s.courses.sort(function (a, b) { return a.endL - b.endL || a.id - b.id; });
      out.set(seg, { level: stats(s.levels), change: { n: s.changes.length, median: median(s.changes) }, courses: s.courses });
    });
    return out;
  }

  var api = { median: median, classify: classify, formatDelay: formatDelay, formatChange: formatChange, formatDuration: formatDuration, inSelection: inSelection, crossesPastLastDay: crossesPastLastDay, summarize: summarize };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.ZtmAggregate = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
