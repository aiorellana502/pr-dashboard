import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizeSnapshot, freshness, render } from '../site/app.mjs';

const row = { repository: 'a/b', number: 1, title: '<img src=x onerror=alert(1)>',
  state: 'Open', review: 'No decisive human review', checks: 'Not reported',
  url: 'https://github.com/a/b/pull/1' };
const snapshot = { generatedAt: '2026-01-01T00:00:00Z', prs: [row] };

test('rejects malformed snapshots and unsafe links instead of rendering fresh totals', () => {
  assert.equal(normalizeSnapshot(snapshot).prs[0].title, row.title);
  for (const value of [{}, { ...snapshot, generatedAt: 'bad' }, { ...snapshot, prs: [] },
    { ...snapshot, prs: [{ ...row, url: 'javascript:alert(1)' }] },
    { ...snapshot, prs: [{ ...row, state: 'Ready to merge' }] }]) {
    assert.throws(() => normalizeSnapshot(value));
  }
});

test('freshness distinguishes a current snapshot, stale snapshot, and a future clock', () => {
  assert.equal(freshness(snapshot.generatedAt, Date.parse(snapshot.generatedAt)).stale, false);
  assert.equal(freshness(snapshot.generatedAt, Date.parse(snapshot.generatedAt) + 3 * 3600000 + 1).stale, true);
  assert.match(freshness(snapshot.generatedAt, Date.parse(snapshot.generatedAt) - 600000).text, /clock/i);
});

class Element {
  children = [];
  textContent = '';
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  setAttribute(name, value) { this[name] = value; }
  set innerHTML(_) { throw new Error('Unsafe HTML interpolation'); }
}

test('public renderer uses text, actual states, and no fabricated approval', () => {
  const ids = new Map();
  const doc = { createElement: () => new Element(), getElementById: id => {
    if (!ids.has(id)) ids.set(id, new Element());
    return ids.get(id);
  } };
  render(snapshot, doc);
  assert.equal(ids.get('total').textContent, '1');
  assert.equal(ids.get('open').textContent, '1');
  assert.equal(ids.get('merged').textContent, '0');
  const cells = ids.get('rows').children[0].children;
  assert.equal(cells[0].children[0].textContent, '#1 · ' + row.title);
  assert.equal(cells[0].children[0].href, row.url);
  assert.equal(cells[2].textContent, 'No decisive human review');
  assert.equal(cells[3].textContent, 'Not reported');
});
