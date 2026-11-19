/* Pobiera plik danych `*.json.gz` i zwraca sparsowany JSON. Działa w oknie i w Web Workerze.
   Pliki leżą w storage jako surowy gzip (bez Content-Encoding), więc rozpakowuje je przeglądarka przez DecompressionStream.
   Jeśli serwer mimo to ustawi Content-Encoding (przeglądarka rozpakowała już treść), JSON jest czytany wprost. */
(function (root) {
  function json(url) {
    return fetch(url).then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status + ' dla ' + url);
      if (r.headers.get('Content-Encoding') || !/\.gz$/.test(url.split(/[?#]/)[0])) return r.json();
      if (typeof DecompressionStream !== 'function') throw new Error('Przeglądarka nie obsługuje DecompressionStream (wymagany do odczytu danych gzip)');
      return new Response(r.body.pipeThrough(new DecompressionStream('gzip'))).json();
    });
  }
  root.ZtmFetch = { json: json };
})(typeof self !== 'undefined' ? self : this);
