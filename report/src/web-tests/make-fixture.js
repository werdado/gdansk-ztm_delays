// Ręcznie budowany raport zgodny z FORMAT.md (niezależny od potoku Pythona).
const fs = require('fs'), path = require('path');
const out = process.argv[2] || path.join(__dirname, 'fixtures', 'report');
fs.rmSync(out, { recursive: true, force: true });
const w = (p, o) => { const f = path.join(out, p); fs.mkdirSync(path.dirname(f), { recursive: true }); fs.writeFileSync(f, JSON.stringify(o)); };

const DAY0 = Math.floor(Date.UTC(2026, 10, 4) / 86400000); // 2026-11-04 jako numer doby
const dates = [0, 1, 2].map(i => new Date((DAY0 + i) * 86400000).toISOString().slice(0, 10));
let seed = 7; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;

function mkSegs(base, ids, latLon0, step, names, dir) {
  return ids.map((id, i) => {
    const a = [latLon0[0] + step[0] * i, latLon0[1] + step[1] * i], b = [a[0] + step[0], a[1] + step[1]];
    return { id, dir, from: { stop_id: String(id * 10), name: names[i], lat: a[0], lon: a[1] },
      to: { stop_id: String(id * 10 + 1), name: names[i + 1], lat: b[0], lon: b[1] }, length_m: 400 + 60 * i,
      path: [a, [(a[0] + b[0]) / 2 + 0.0005, (a[1] + b[1]) / 2], b] };
  });
}
const evil = '<img src=x onerror="window.__xss=1">Jasień PKM';
const lines = [
  { name: '127', slug: '127', skipped: 12, variants: [
    { key: '202-41', dir: 0, headsign: evil, segs: [0, 1, 2, 3, 4], status: 'ok' },
    { key: '301-42', dir: 0, headsign: 'Jasień skrót', segs: [0, 1, 2, 5, 6], status: 'ok' },
    { key: '202-51', dir: 1, headsign: 'Oliwa PKP', segs: [10, 11, 12, 13], status: 'ok' },
    { key: '202-99', dir: 1, headsign: 'Oliwa PKP', segs: [], status: 'absent_in_gtfs' } ],
    segments: [
      ...mkSegs(0, [0, 1, 2, 3, 4], [54.34, 18.57], [0.004, 0.005], ['Oliwa PKP 04', 'Oliwa PKP 02', 'Opata 01', 'Kołobrzeska 01', 'Chrzanowskiego 01', 'Jasień PKM 01'], 0),
      ...mkSegs(0, [5, 6], [54.346, 18.595], [0.003, 0.004], ['Kołobrzeska 01', 'Skrót 01', 'Jasień skrót 01'], 0),
      ...mkSegs(0, [10, 11, 12, 13], [54.36, 18.6], [-0.004, -0.005], ['Jasień PKM 02', 'A 02', 'B 02', 'C 02', 'Oliwa PKP 02'], 1) ] },
  { name: 'N8', slug: 'N8', skipped: 0, variants: [
    { key: '808-11', dir: 0, headsign: 'Brzeźno', segs: [0, 1, 2], status: 'ok' } ],
    segments: mkSegs(0, [0, 1, 2], [54.4, 18.65], [0.003, -0.004], ['Dworzec', 'Plac', 'Rynek', 'Brzeźno'], 0) },
];

const manifest = { format: 1, generated: '2026-11-12T14:00:00Z', rules_version: '1',
  range: { from: dates[0], to: dates[2], days: dates, skipped_days: ['2026-11-03', '2026-11-11'] }, params: { match_max_dist_m: 75 }, lines: [], quality: 'data/quality.json' };
let courseId = 1;
const srcTpl = (d, i) => ({ snapshot: `snapshots/gps/${d}/${d}T08:${String(i % 60).padStart(2, '0')}:00.000Z/a${i}.json.gz`, manifest: `runs/${d}/${d}T08:${String(i % 60).padStart(2, '0')}:00.000Z/a${i}.json`, run_status: i % 17 === 0 ? 'partial' : 'complete', source_status: 'stored', url: 'https://ckan2.multimediagdansk.pl/gpsPositions?v=2', fetchedAt: d + 'T08:00:00.000Z', receivedAt: d + 'T08:00:01.000Z', storedAt: d + 'T08:00:02.000Z', provenance_gap: false });

for (const ln of lines) {
  const segById = Object.fromEntries(ln.segments.map(s => [s.id, s]));

    w(`data/lines/${ln.slug}/geometry.json`, { format: 1, segments: ln.segments, variants: ln.variants.map(v => ({ key: v.key, dir: v.dir, headsign: v.headsign, segments: v.segs })) });
  const perDay = Object.fromEntries(dates.map(d => [d, { courses: [], c: { course: [], seg: [], endL: [], end: [], startL: [], start: [], dist: [] } }]));
  const counts = {};
  dates.forEach((d, di) => {
    for (const v of ln.variants) {
      counts[v.key] = counts[v.key] || { courses: 0, observations: 0 };
      for (let k = 0; k < 8; k++) {
        const id = courseId++, hour = 6 + k * 2 + (v.dir ? 1 : 0), startL = (DAY0 + di) * 86400 + hour * 3600;
        const crs = { id, dir: v.dir, variant: v.key, startL, vehicle: String(145000 + id), service: ln.name + '-0' + (1 + k % 3) };
        counts[v.key].courses++;
        const obs = [], segs = [], srcs = [];
        const mkSrc = i => { srcs.push(srcTpl(d, srcs.length + id)); return srcs.length - 1; };
        let t = startL - 120, delay = Math.round((rnd() * 4 - 1) * 60 + (k === 3 ? 400 : 0));
        const base = v.segs.length ? segById[v.segs[0]] : { from: { lat: 54.3, lon: 18.5 } };
        for (let i = 0; i < 2; i++) { obs.push({ tL: t, tU: t - 3600, delay: delay, speed: 0, lat: base.from.lat, lon: base.from.lon, s: 0, seg: v.segs[0] ?? null, phase: 'pre_departure', flags: [], src: [mkSrc()] }); t += 40; }
        if (!v.segs.length) { for (let i = 0; i < 5; i++) { obs.push({ tL: t, tU: t - 3600, delay: delay, speed: 20, lat: 54.3 + i * .001, lon: 18.5, s: null, seg: null, phase: 'unknown', flags: ['unmatched'], src: [mkSrc()] }); t += 40; } }
        let cum = 0, prevEnd = null;
        v.segs.forEach((sid, si) => {
          const sg = segById[sid]; let startRef = prevEnd;
          let endIdx = null;
          for (let j = 0; j < 4; j++) {
            delay += Math.round(rnd() * 50 - 15); t += 35;
            const f = (j + 1) / 4;
            const o = { tL: t, tU: t - 3600, delay, speed: 25, lat: sg.from.lat + (sg.to.lat - sg.from.lat) * f, lon: sg.from.lon + (sg.to.lon - sg.from.lon) * f, s: cum + sg.length_m * f, seg: sid, phase: 'en_route', flags: [], src: [mkSrc()] };
            obs.push(o); if (j === 2) endIdx = obs.length - 1;
          }
          const skipChance = (id + si) % 7 === 0; // brak wartości na odcinku
          const eo = obs[endIdx];
          if (skipChance) { segs.push({ seg: sid, end: null, start: startRef ? { obs: startRef.obs, delay: startRef.delay, kind: 'prev_end' } : null, change: null, note: 'przejechany w całości między obserwacjami' }); prevEnd = null; }
          else {
            const hasStart = startRef !== null || si === 0;
            const startObs = startRef || (si === 0 ? { obs: 1, delay: obs[1].delay } : null);
            const change = hasStart && startObs ? eo.delay - startObs.delay : null;
            segs.push({ seg: sid, end: { obs: endIdx, delay: eo.delay, dist_m: 12 + si * 3, gap_s: 20 }, start: startObs ? { obs: startObs.obs, delay: startObs.delay, kind: startRef ? 'prev_end' : 'course_start' } : null, change, note: null });
            const di2 = Math.floor(eo.tL / 86400) - DAY0, dd = dates[di2] || d;
            const pd = perDay[dd]; let ci = pd.courses.findIndex(c => c.id === id); if (ci < 0) { pd.courses.push(crs); ci = pd.courses.length - 1; }
            pd.c.course.push(ci); pd.c.seg.push(sid); pd.c.endL.push(eo.tL); pd.c.end.push(eo.delay);
            pd.c.startL.push(change === null ? null : obs[startObs.obs].tL); pd.c.start.push(change === null ? null : startObs.delay); pd.c.dist.push(12 + si * 3);
            prevEnd = { obs: endIdx, delay: eo.delay };
          }
          cum += sg.length_m;
        });
        let arrival = null;
        if (v.segs.length) {
          const last = obs[obs.length - 1]; arrival = id % 5 === 0 ? { obs: null, delay: null, uncertain: 'Pierwsza obserwacja przy krańcu już w postoju — dojazd nieznany.' } : { obs: obs.length - 1, delay: last.delay, uncertain: null };
          const sg = segById[v.segs[v.segs.length - 1]];
          for (let i = 0; i < 3; i++) { t += 40; obs.push({ tL: t, tU: t - 3600, delay: 0, speed: 0, lat: sg.to.lat, lon: sg.to.lon, s: cum, seg: null, phase: 'terminal_after_arrival', flags: [], src: [mkSrc()] }); }
        }
        counts[v.key].observations += obs.length;
        const truncated = (di === 0 && k === 0) ? 'start' : null;
        w(`data/lines/${ln.slug}/courses/${id}.json`, { format: 1, id, line: ln.name, dir: v.dir, variant: v.key, headsign: v.headsign, vehicle: crs.vehicle, service: crs.service, startL, truncated, variant_status: v.status, segments: segs, arrival, observations: obs, sources: srcs });
      }
    }
  });
  const days = {};
  for (const d of dates) { w(`data/lines/${ln.slug}/days/${d}.json`, { format: 1, line: ln.name, date: d, courses: perDay[d].courses, c: perDay[d].c }); days[d] = `data/lines/${ln.slug}/days/${d}.json`; }
  const dirs = [...new Set(ln.variants.map(v => v.dir))].map(dir => {
    const vs = ln.variants.filter(v => v.dir === dir);
    return { id: dir, label: vs[0].headsign, other_headsigns: [...new Set(vs.map(v => v.headsign).filter(h => h !== vs[0].headsign))],
      variants: vs.map(v => ({ key: v.key, route_id: 1, trip_id: 1, headsign: v.headsign, in_gtfs: v.status !== 'absent_in_gtfs', status: v.status, courses: counts[v.key].courses, observations: counts[v.key].observations })) };
  });
  manifest.lines.push({ name: ln.name, slug: ln.slug, skipped_records: ln.skipped, courses: Object.values(counts).reduce((a, c) => a + c.courses, 0), directions: dirs, geometry: `data/lines/${ln.slug}/geometry.json`, days });
}
w('data/manifest.json', manifest);
w('data/quality.json', { format: 1, inputs: { archive: '/workspace', gtfs: 'gtfsgoogle.zip', gtfs_feed_end_date: '20261125' },
  range: { from: dates[0], to: dates[2], skipped_days: [{ date: '2026-11-03', reason: 'niepełna doba na początku archiwum' }] },
  counts: { source_records: 100, snapshots_read: 99, snapshot_errors: 1, provenance_gaps: 0, raw_records: 5000, observations: 4000, conflicts: 3, without_trip: 12 },
  lines: { '127': { skipped_records: 12, raw_skipped_records: 15, courses: 48, variants_absent_in_gtfs: [{ variant: '99', courses: 1, observations: 10 }], segment_coverage: { '1': { passes: 10, with_value: 8, with_change: 7 } } } },
  notes: ['Fixture testowy — dane nie są rzeczywiste.'] });
// kopia zasobów aplikacji
const web = path.join(__dirname, '..', 'src', 'ztm_viz', 'web');
fs.cpSync(web, out, { recursive: true });
console.log('fixture:', out);
