// Scenariusze przeglądarkowe przez HTTP pod podkatalogiem: node make-fixture.js && node e2e.js [katalog-raportu]
const http = require('http'), fs = require('fs'), path = require('path'), assert = require('assert');
const { chromium } = require('playwright');
const root = path.resolve(process.argv[2] || path.join(__dirname, 'fixtures', 'report'));
const PREFIX = '/prefix/deep/';
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.png': 'image/png' };
const server = http.createServer((req, res) => {
  const u = decodeURIComponent(req.url.split('?')[0]);
  if (!u.startsWith(PREFIX)) { res.writeHead(404); return res.end('nie ma'); }
  let f = path.join(root, u.slice(PREFIX.length)); if (f.endsWith(path.sep) || u === PREFIX) f = path.join(f, 'index.html');
  if (!f.startsWith(root) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); return res.end('nie ma'); }
  res.writeHead(200, { 'content-type': MIME[path.extname(f)] || 'application/octet-stream' }); fs.createReadStream(f).pipe(res);
});
const shots = path.join(__dirname, 'shots'); fs.mkdirSync(shots, { recursive: true });
const ok = (m) => console.log('  ✔', m);

(async () => {
  await new Promise(r => server.listen(0, '127.0.0.1', r));
  const base = `http://127.0.0.1:${server.address().port}${PREFIX}`;
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();
  const errors = []; page.on('pageerror', e => errors.push(String(e)));
  let tileReqs = 0;
  await ctx.route(/tile\.openstreetmap\.org/, r => { tileReqs++; r.abort(); });
  const external = []; page.on('request', r => { if (!r.url().startsWith('http://127.0.0.1') && !/openstreetmap/.test(r.url()) && !r.url().startsWith('data:')) external.push(r.url()); });

  await page.goto(base);
  await page.waitForFunction(() => /Kursów z danymi/.test(document.getElementById('active-filter').textContent), null, { timeout: 15000 });
  ok('pierwszy widok pod podkatalogiem');
  const lines = await page.$$eval('#f-line option', o => o.map(x => x.value));
  assert.deepStrictEqual(lines, ['127', 'N8']); ok('lista linii pochodzi z manifestu (127, N8)');
  const af = await page.textContent('#active-filter');
  assert.match(af, /wszystkie dni/); ok('domyślnie cały okres: ' + af.slice(0, 90));
  assert.strictEqual(await page.evaluate(() => window.__xss), undefined); ok('tekst ze źródła nie wykonuje HTML');
  assert.ok((await page.textContent('#charts')).includes('<img src=x')); ok('nazwa ze znacznikami pokazana jako tekst');
  assert.ok(await page.$('#map .leaflet-tile-pane')); await page.waitForSelector('#tile-note:not([hidden])', { timeout: 8000 }); ok('podkład niedostępny: komunikat, reszta działa (żądań kafelków: ' + tileReqs + ')');
  await page.screenshot({ path: path.join(shots, 'desktop-summary.png'), fullPage: true });

  // odcinek -> szczegóły -> kurs
  await page.click('#charts g.bar-g >> nth=1');
  await page.waitForSelector('#details .kv');
  assert.match(await page.textContent('#details'), /Kursów, dla których znana jest zmiana/); ok('szczegóły odcinka');
  assert.match(page.url(), /seg=/);
  const hashBefore = new URL(page.url()).hash;
  await page.click('#details tbody tr >> nth=0 >> button');
  await page.waitForSelector('#course-view .card h2');
  assert.match(await page.textContent('#course-view'), /Pełny kurs/); assert.match(await page.textContent('#course-view'), /przed odjazdem/);
  assert.match(page.url(), /course=\d+/); ok('widok kursu: pełny kurs, obserwacje przed odjazdem');
  await page.screenshot({ path: path.join(shots, 'desktop-course.png'), fullPage: true });
  await page.click('text=← Wróć do podsumowania');
  await page.waitForSelector('#summary-view:not([hidden])'); await page.waitForSelector('#details .kv');
  assert.strictEqual(new URL(page.url()).hash, hashBefore); ok('powrót zachowuje wybór');

  // filtry godzin i dni
  await page.selectOption('#f-from', '8'); await page.selectOption('#f-to', '10');
  await page.waitForFunction(() => /8:00–10:00/.test(document.getElementById('active-filter').textContent));
  await page.uncheck('#f-days input >> nth=0');
  await page.waitForFunction(() => /dni: 05\.11, 06\.11/.test(document.getElementById('active-filter').textContent));
  ok('filtry godzin i dni w aktywnym opisie i w adresie: ' + new URL(page.url()).hash);
  // przez północ na ostatnim dniu
  await page.selectOption('#f-from', '22'); await page.selectOption('#f-to', '2');
  await page.waitForSelector('#midnight-note:not([hidden])'); ok('uwaga o nocy po ostatniej dobie');
  await page.goto(base + '#line=127&dir=0'); await page.waitForSelector('#midnight-note[hidden]', { state: 'attached' });

  // wariant nieobecny w rozkładzie
  await page.selectOption('#f-dir', '1'); await page.selectOption('#f-variant', '202-99');
  await page.waitForSelector('#charts .notice');
  assert.match(await page.textContent('#charts'), /nieobecny w pomocniczym rozkładzie/); ok('wariant bez geometrii opisany');

  // druga linia z nazwą alfanumeryczną
  await page.selectOption('#f-line', 'N8');
  await page.waitForFunction(() => /Linia N8/.test(document.getElementById('active-filter').textContent)); ok('linia N8');

  // błąd pobrania kursu i ponowienie
  let fail = true; await page.route(/courses\/\d+\.json\.gz/, r => { if (fail) r.abort(); else r.continue(); });
  await page.goto(base + '#line=127&dir=0&course=5'); await page.waitForSelector('#course-view .notice.error');
  assert.match(await page.textContent('#course-view'), /Nie udało się pobrać/);
  fail = false; await page.click('text=Spróbuj ponownie'); await page.waitForSelector('#course-view .kv'); ok('błąd pobrania kursu i udane ponowienie');

  // poprawne ponowne otwarcie przez adres
  await page.goto(base + '#line=N8&dir=0&seg=1'); await page.waitForSelector('#details .kv'); ok('odtworzenie stanu z adresu');

  // mały ekran
  const small = await browser.newContext({ viewport: { width: 400, height: 800 } });
  await small.route(/tile\.openstreetmap\.org/, r => r.abort());
  const sp = await small.newPage(); await sp.goto(base);
  await sp.waitForFunction(() => /Kursów z danymi/.test(document.getElementById('active-filter').textContent));
  const overflow = await sp.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  assert.ok(overflow <= 1, 'poziome przewijanie strony: ' + overflow); ok('400 px bez poziomego przewijania strony');
  await sp.screenshot({ path: path.join(shots, 'mobile-summary.png'), fullPage: true });
  await sp.goto(base + '#line=127&dir=0&course=3'); await sp.waitForSelector('#course-view .kv');
  assert.ok((await sp.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)) <= 1);
  await sp.screenshot({ path: path.join(shots, 'mobile-course.png'), fullPage: true });

  // file://
  const fp = await ctx.newPage(); await fp.goto('file://' + path.join(root, 'index.html'));
  assert.ok(await fp.isVisible('#file-notice')); assert.match(await fp.textContent('#file-notice'), /HTTP/); ok('file:// pokazuje informację o HTTP');

  assert.deepStrictEqual(errors, [], 'błędy JS: ' + errors.join('; '));
  assert.deepStrictEqual(external, [], 'nieoczekiwane żądania zewnętrzne: ' + external.join(', '));
  await browser.close(); server.close(); console.log('OK');
})().catch(e => { console.error('FAIL', e); process.exit(1); });
