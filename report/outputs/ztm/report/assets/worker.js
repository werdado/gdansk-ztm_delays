/* Web Worker: wczytuje pakiety dobowe linii i liczy agregaty (z aggregate.js). */
importScripts('fetchjson.js', 'aggregate.js');
var cache = {}; // linia -> Promise<pakiety>

function loadLine(key, urls) {
  if (!cache[key]) {
    cache[key] = Promise.all(urls.map(function (u) {
      return ZtmFetch.json(u);
    })).catch(function (e) { delete cache[key]; throw e; });
  }
  return cache[key];
}

self.onmessage = function (ev) {
  var m = ev.data;
  loadLine(m.line, m.urls).then(function (days) {
    var sel = { days: m.sel.days ? new Set(m.sel.days) : null, from: m.sel.from, to: m.sel.to };
    var res = ZtmAggregate.summarize(days, { sel: sel, dir: m.dir, variant: m.variant });
    var arr = [];
    res.forEach(function (v, k) { arr.push([k, v]); });
    self.postMessage({ id: m.id, ok: true, result: arr });
  }).catch(function (e) {
    self.postMessage({ id: m.id, ok: false, error: String(e && e.message || e) });
  });
};
