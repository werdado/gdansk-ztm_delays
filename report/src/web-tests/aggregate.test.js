const test = require('node:test');
const assert = require('node:assert');
const A = require('../src/ztm_viz/web/assets/aggregate.js');

const H = 3600;
const DAY0 = 20000; // local day number
const L = (dayOff, h, m = 0) => (DAY0 + dayOff) * 86400 + h * H + m * 60;

// Build a day bundle (FORMAT.md) from rows [course, seg, endL, end, startL, start]
function bundle(courses, rows) {
  const c = { course: [], seg: [], endL: [], end: [], startL: [], start: [], dist: [] };
  for (const r of rows) {
    c.course.push(r[0]); c.seg.push(r[1]); c.endL.push(r[2]); c.end.push(r[3]);
    c.startL.push(r[4] === undefined ? null : r[4]); c.start.push(r[5] === undefined ? null : r[5]);
    c.dist.push(10);
  }
  return { format: 1, courses, c };
}
const crs = (id, dir = 0, variant = 'v') => ({ id, dir, variant, startL: 0, vehicle: 'x', service: 's' });
const ALL = { days: null, from: 0, to: 86400 };

test('median: odd, even (mean of two middle), empty', () => {
  assert.strictEqual(A.median([3, 1, 2]), 2);
  assert.strictEqual(A.median([300, 301]), 300.5);
  assert.strictEqual(A.median([]), null);
});

test('classify: -30,0,300,301 and 300.5 before rounding', () => {
  assert.strictEqual(A.classify(-30), 'green');
  assert.strictEqual(A.classify(0), 'green');
  assert.strictEqual(A.classify(1), 'orange');
  assert.strictEqual(A.classify(300), 'orange');
  assert.strictEqual(A.classify(301), 'red');
  assert.strictEqual(A.classify(300.5), 'red');
  assert.strictEqual(A.classify(null), 'grey');
});

test('formatDelay: text carries the meaning, negatives are "przed czasem"', () => {
  assert.match(A.formatDelay(-30), /przed czasem/);
  assert.match(A.formatDelay(300), /5 min/);
  assert.strictEqual(A.formatDelay(null), 'brak danych');
});

test('change within course: 2->5 min = +3 min; 8->5 = -3 min', () => {
  const b = bundle([crs(1), crs(2)], [
    [0, 7, L(0, 8, 5), 300, L(0, 8, 0), 120],
    [1, 8, L(0, 9, 5), 300, L(0, 9, 0), 480],
  ]);
  const r = A.summarize([b], { sel: ALL });
  assert.strictEqual(r.get(7).level.median, 300);
  assert.strictEqual(r.get(7).change.median, 180);
  assert.strictEqual(r.get(8).change.median, -180);
});

test('change is median of per-course changes, not difference of medians', () => {
  const b = bundle([crs(1), crs(2), crs(3)], [
    [0, 1, L(0, 8), 100, L(0, 7), 0],     // +100
    [1, 1, L(0, 8), 200, L(0, 7), 190],   // +10
    [2, 1, L(0, 8), 900, L(0, 7), 800],   // +100
  ]);
  const s = A.summarize([b], { sel: ALL }).get(1);
  assert.strictEqual(s.level.median, 200);
  assert.strictEqual(s.change.median, 100); // diff of medians would be 200-190=10
  assert.strictEqual(s.level.max, 900);
});

test('duplicate record for same course+segment counts once', () => {
  const row = [0, 1, L(0, 8), 100, L(0, 7), 0];
  const b = bundle([crs(1)], [row, row.slice()]);
  const b2 = bundle([crs(1)], [row.slice()]);
  const s = A.summarize([b, b2], { sel: ALL }).get(1);
  assert.strictEqual(s.level.n, 1);
  assert.strictEqual(s.change.n, 1);
});

test('missing start: level kept, change dropped, counts distinct', () => {
  const b = bundle([crs(1), crs(2)], [
    [0, 1, L(0, 8), 100, L(0, 7), 40],
    [1, 1, L(0, 8, 30), 500, null, null],
  ]);
  const s = A.summarize([b], { sel: ALL }).get(1);
  assert.strictEqual(s.level.n, 2);
  assert.strictEqual(s.change.n, 1);
  assert.strictEqual(s.change.median, 60);
});

test('time filter: level needs end in range; change needs both ends in range', () => {
  const b = bundle([crs(1)], [[0, 1, L(0, 8, 30), 100, L(0, 7, 50), 40]]);
  const sel = { days: new Set([DAY0]), from: 8 * H, to: 9 * H };
  const s = A.summarize([b], { sel }).get(1);
  assert.strictEqual(s.level.n, 1);
  assert.strictEqual(s.change.n, 0);
  assert.strictEqual(s.change.median, null);
});

test('inSelection: left-closed hour interval and selected days', () => {
  const sel = { days: new Set([DAY0]), from: 8 * H, to: 9 * H };
  assert.ok(A.inSelection(L(0, 8), sel));
  assert.ok(!A.inSelection(L(0, 9), sel));
  assert.ok(!A.inSelection(L(1, 8, 30), sel));
});

test('inSelection: range across midnight belongs to the night started on selected day', () => {
  const fri = DAY0, sat = DAY0 + 1;
  const sel = { days: new Set([fri]), from: 22 * H, to: 2 * H };
  assert.ok(A.inSelection(L(0, 22), sel));
  assert.ok(A.inSelection(L(1, 1, 59), sel));
  assert.ok(!A.inSelection(L(1, 2), sel));
  assert.ok(!A.inSelection(L(0, 1), sel));      // early Friday belongs to Thursday's night
  assert.ok(!A.inSelection(L(1, 22), sel));      // Saturday evening: Saturday not selected
  assert.ok(sat > fri);
});

test('crossesPastLastDay: night of last processed day extends outside range', () => {
  const sel = { days: new Set([DAY0 + 2]), from: 22 * H, to: 2 * H };
  assert.ok(A.crossesPastLastDay(sel, DAY0 + 2));
  assert.ok(!A.crossesPastLastDay(sel, DAY0 + 3));
  assert.ok(!A.crossesPastLastDay({ days: new Set([DAY0 + 2]), from: 8 * H, to: 9 * H }, DAY0 + 2));
});

test('direction and variant filters', () => {
  const b = bundle([crs(1, 0, 'a'), crs(2, 1, 'b')], [
    [0, 1, L(0, 8), 10, null, null],
    [1, 1, L(0, 8), 20, null, null],
  ]);
  assert.strictEqual(A.summarize([b], { sel: ALL, dir: 1 }).get(1).level.n, 1);
  assert.strictEqual(A.summarize([b], { sel: ALL, variant: 'a' }).get(1).level.median, 10);
  assert.strictEqual(A.summarize([b], { sel: ALL }).get(1).level.n, 2);
});

test('segment course list carries per-course level and change', () => {
  const b = bundle([crs(5)], [[0, 1, L(0, 8), 100, L(0, 7), 40]]);
  const s = A.summarize([b], { sel: ALL }).get(1);
  assert.deepStrictEqual(s.courses.map(c => [c.id, c.end, c.change]), [[5, 100, 60]]);
});
