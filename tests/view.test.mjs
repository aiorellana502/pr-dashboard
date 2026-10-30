import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizeSnapshot, freshness, render } from '../site/app.mjs';

const row = { repository: 'a/b', number: 1, title: '<img src=x onerror=alert(1)>',
  state: 'Open', review: 'No decisive human review', checks: 'Not reported',
  url: 'https://github.com/a/b/pull/1', explanation: '<img src=x onerror=alert(1)>' };
const issue = { repository: 'a/b', number: 2, title: row.title, state: 'Open',
  url: 'https://github.com/a/b/issues/2', labels: ['bug', row.title], explanation: row.explanation };
const snapshot = { generatedAt: '2026-01-01T00:00:00Z', prs: [row], issues: [issue] };

test('rejects malformed snapshots and unsafe links instead of rendering fresh totals', () => {
  assert.equal(normalizeSnapshot(snapshot).prs[0].title, row.title);
  for (const value of [{}, { ...snapshot, generatedAt: 'bad' }, { ...snapshot, prs: [], issues: [] },
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
  assert.equal(cells.length, 4);
  assert.equal(cells[0].children[1].textContent, row.explanation);
  assert.equal(cells[0].children[1].class, 'explain');
});

test('validates issues and bounded explanations for both item types', () => {
  for (const key of ['prs', 'issues']) {
    const item = key === 'prs' ? row : issue;
    for (const explanation of [undefined, '', 123, 'x'.repeat(401)]) {
      assert.throws(() => normalizeSnapshot({ ...snapshot, [key]: [{ ...item, explanation }] }));
    }
    assert.equal(normalizeSnapshot({ ...snapshot, [key]: [{ ...item, explanation: 'x'.repeat(400) }] })[key][0].explanation.length, 400);
    for (const value of [undefined, null, {}]) {
      assert.throws(() => normalizeSnapshot({ ...snapshot, [key]: value }));
    }
  }
  for (const change of [
    { state: undefined }, { state: 'Draft' }, { state: 'Merged' },
    { url: 'javascript:alert(1)' }, { url: row.url },
    { labels: ['bug', 1] }, { labels: [''] }, { labels: null },
    { repository: '' }, { number: 0 }, { title: null },
  ]) {
    assert.throws(() => normalizeSnapshot({ ...snapshot, issues: [{ ...issue, ...change }] }));
  }
  assert.equal(normalizeSnapshot({ ...snapshot, prs: [] }).issues.length, 1);
  assert.equal(normalizeSnapshot({ ...snapshot, issues: [] }).prs.length, 1);
  assert.deepEqual(normalizeSnapshot(snapshot).issues[0], issue);
});

test('renders mixed issue states, labels and explanations as literal text', () => {
  const ids = new Map();
  const doc = { createElement: () => new Element(), getElementById: id => {
    if (!ids.has(id)) ids.set(id, new Element());
    return ids.get(id);
  } };
  const mixed = { ...snapshot, issues: [issue, { ...issue, number: 3,
    url: 'https://github.com/a/b/issues/3', state: 'Closed', labels: [] }] };
  render(normalizeSnapshot(mixed), doc);
  assert.equal(ids.get('issues-total').textContent, '2');
  assert.equal(ids.get('issues-open').textContent, '1');
  assert.equal(ids.get('issues-closed').textContent, '1');
  const rows = ids.get('issue-rows').children;
  assert.equal(rows.length, 2);
  const cells = rows[0].children;
  assert.equal(cells.length, 3);
  assert.equal(cells[0].children.length, 2);
  assert.equal(cells[0].children[0].textContent, '#2 · ' + issue.title);
  assert.equal(cells[0].children[0].href, issue.url);
  assert.equal(cells[0].children[0].rel, 'noopener');
  assert.equal(cells[0].children[1].textContent, issue.explanation);
  assert.equal(cells[0].children[1].class, 'explain');
  assert.equal(cells[1].textContent, 'Open');
  assert.equal(cells[2].textContent, issue.labels.join(', '));
  assert.equal(rows[1].children[1].textContent, 'Closed');
  assert.equal(rows[1].children[2].textContent, '—');
  render({ ...snapshot, issues: [] }, doc);
  assert.equal(ids.get('issue-rows').children.length, 0);
  assert.equal(ids.get('issues-total').textContent, '0');
});
