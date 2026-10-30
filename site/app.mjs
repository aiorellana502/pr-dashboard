const VALID_STATES = new Set(['Open', 'Draft', 'Merged', 'Closed']);
const STALE_THRESHOLD_MS = 3 * 3600000;

function isSafePullUrl(url) {
  return typeof url === 'string' && /^https:\/\/github\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+\/pull\/\d+$/.test(url);
}

function isSafeIssueUrl(url) {
  return typeof url === 'string' && /^https:\/\/github\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+\/issues\/\d+$/.test(url);
}

function validateExplanation(explanation) {
  if (typeof explanation !== 'string' || !explanation || explanation.length > 400) {
    throw new Error('Invalid explanation');
  }
}

export function normalizeSnapshot(snapshot) {
  if (!snapshot || typeof snapshot !== 'object') throw new Error('Invalid snapshot');
  const { generatedAt, prs, issues } = snapshot;
  if (typeof generatedAt !== 'string' || Number.isNaN(Date.parse(generatedAt))) {
    throw new Error('Invalid snapshot timestamp');
  }
  if (!Array.isArray(prs) || !Array.isArray(issues)) {
    throw new Error('Invalid snapshot items');
  }
  if (prs.length + issues.length === 0) throw new Error('Snapshot has no items');
  const normalizedPrs = prs.map((row) => {
    if (!row || typeof row !== 'object') throw new Error('Invalid pull request entry');
    const { repository, number, title, state, review, checks, url, explanation } = row;
    if (typeof repository !== 'string' || !repository) throw new Error('Invalid repository');
    if (!Number.isInteger(number) || number < 1) throw new Error('Invalid pull request number');
    if (typeof title !== 'string') throw new Error('Invalid pull request title');
    if (!VALID_STATES.has(state)) throw new Error('Invalid pull request state');
    if (typeof review !== 'string') throw new Error('Invalid review signal');
    if (typeof checks !== 'string') throw new Error('Invalid checks signal');
    if (!isSafePullUrl(url)) throw new Error('Invalid pull request url');
    validateExplanation(explanation);
    return { repository, number, title, state, review, checks, url, explanation };
  });
  const normalizedIssues = issues.map((row) => {
    if (!row || typeof row !== 'object') throw new Error('Invalid issue entry');
    const { repository, number, title, state, url, labels, explanation } = row;
    if (typeof repository !== 'string' || !repository) throw new Error('Invalid repository');
    if (!Number.isInteger(number) || number < 1) throw new Error('Invalid issue number');
    if (typeof title !== 'string') throw new Error('Invalid issue title');
    if (state !== 'Open' && state !== 'Closed') throw new Error('Invalid issue state');
    if (!isSafeIssueUrl(url)) throw new Error('Invalid issue url');
    if (!Array.isArray(labels) || labels.some(label => typeof label !== 'string' || !label)) {
      throw new Error('Invalid issue labels');
    }
    validateExplanation(explanation);
    return { repository, number, title, state, url, labels, explanation };
  });
  return { generatedAt, prs: normalizedPrs, issues: normalizedIssues };
}

export function freshness(generatedAt, now = Date.now()) {
  const generatedMs = Date.parse(generatedAt);
  const diffMs = now - generatedMs;
  if (diffMs < 0) {
    return { stale: false, text: 'Snapshot looks newer than this device clock; check your clock.' };
  }
  if (diffMs > STALE_THRESHOLD_MS) {
    const hours = Math.floor(diffMs / 3600000);
    return { stale: true, text: `Stale: last successful snapshot is ${hours}h old.` };
  }
  return { stale: false, text: 'Up to date.' };
}

export function render(snapshot, doc) {
  const counts = { total: 0, open: 0, draft: 0, merged: 0, closed: 0 };
  const rowElements = snapshot.prs.map((pr) => {
    counts.total += 1;
    counts[pr.state.toLowerCase()] += 1;

    const link = doc.createElement('a');
    link.textContent = `#${pr.number} · ${pr.title}`;
    link.setAttribute('href', pr.url);
    link.href = pr.url;
    link.setAttribute('rel', 'noopener');

    const prCell = doc.createElement('td');
    const explanation = doc.createElement('p');
    explanation.textContent = pr.explanation;
    explanation.setAttribute('class', 'explain');
    prCell.append(link, explanation);
    const stateCell = doc.createElement('td');
    stateCell.textContent = pr.state;
    const reviewCell = doc.createElement('td');
    reviewCell.textContent = pr.review;
    const checksCell = doc.createElement('td');
    checksCell.textContent = pr.checks;

    const tr = doc.createElement('tr');
    tr.append(prCell, stateCell, reviewCell, checksCell);
    return tr;
  });

  doc.getElementById('total').textContent = String(counts.total);
  doc.getElementById('open').textContent = String(counts.open);
  doc.getElementById('draft').textContent = String(counts.draft);
  doc.getElementById('merged').textContent = String(counts.merged);
  doc.getElementById('closed').textContent = String(counts.closed);
  doc.getElementById('rows').replaceChildren(...rowElements);

  const issueCounts = { total: 0, open: 0, closed: 0 };
  const issueRows = snapshot.issues.map((issue) => {
    issueCounts.total += 1;
    issueCounts[issue.state.toLowerCase()] += 1;
    const link = doc.createElement('a');
    link.textContent = `#${issue.number} · ${issue.title}`;
    link.setAttribute('href', issue.url);
    link.href = issue.url;
    link.setAttribute('rel', 'noopener');
    const explanation = doc.createElement('p');
    explanation.textContent = issue.explanation;
    explanation.setAttribute('class', 'explain');
    const titleCell = doc.createElement('td');
    titleCell.append(link, explanation);
    const stateCell = doc.createElement('td');
    stateCell.textContent = issue.state;
    const labelsCell = doc.createElement('td');
    labelsCell.textContent = issue.labels.length ? issue.labels.join(', ') : '—';
    const tr = doc.createElement('tr');
    tr.append(titleCell, stateCell, labelsCell);
    return tr;
  });
  doc.getElementById('issues-total').textContent = String(issueCounts.total);
  doc.getElementById('issues-open').textContent = String(issueCounts.open);
  doc.getElementById('issues-closed').textContent = String(issueCounts.closed);
  doc.getElementById('issue-rows').replaceChildren(...issueRows);
}

function setMessage(doc, text) {
  doc.getElementById('message').textContent = text;
}

async function loadAndRender(doc) {
  const refreshButton = doc.getElementById('refresh');
  refreshButton.disabled = true;
  try {
    const response = await fetch('./data.json', { cache: 'no-store' });
    if (!response.ok) throw new Error('Snapshot request failed');
    const snapshot = normalizeSnapshot(await response.json());
    render(snapshot, doc);
    const { stale, text } = freshness(snapshot.generatedAt, Date.now());
    doc.getElementById('updated').textContent = new Date(snapshot.generatedAt).toLocaleString();
    doc.getElementById('freshness').textContent = text;
    doc.getElementById('freshness').classList.toggle('stale', stale);
    setMessage(doc, stale ? 'Showing the last successful snapshot; it is older than expected.' : 'Showing the latest published snapshot.');
  } catch {
    setMessage(doc, 'Could not load a snapshot. The previously published page, if any, is unaffected.');
  } finally {
    refreshButton.disabled = false;
  }
}

/* c8 ignore start */
if (typeof document !== 'undefined') {
  const refreshButton = document.getElementById('refresh');
  refreshButton.addEventListener('click', () => loadAndRender(document));
  loadAndRender(document);
  setInterval(() => loadAndRender(document), 5 * 60 * 1000);
}
/* c8 ignore stop */
