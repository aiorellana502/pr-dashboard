"""Collect a complete public PR snapshot; never publish a partial refresh."""
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = 'https://api.github.com'


def validate_watchlist(rows):
    if not isinstance(rows, list) or not rows:
        raise ValueError('Watchlist must be a nonempty list')
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Invalid watchlist entry')
        repo, number = row.get('repository'), row.get('number')
        if not isinstance(repo, str) or not re.fullmatch(r'[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+', repo):
            raise ValueError('Invalid repository')
        if type(number) is not int or number < 1 or (repo.lower(), number) in seen:
            raise ValueError('Invalid or duplicate PR number')
        seen.add((repo.lower(), number))
    return rows


def api(path, key=None):
    """Paginate list endpoints, restricting authenticated requests to GitHub."""
    url = ORIGIN + path + ('&' if '?' in path else '?') + 'per_page=100'
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'personal-pr-dashboard',
               'X-GitHub-Api-Version': '2022-11-28'}
    token = os.environ.get('GITHUB_TOKEN')
    if token:
        headers['Authorization'] = 'Bearer ' + token
    items = []
    for _ in range(100):
        if not url.startswith(ORIGIN + '/repos/'):
            raise RuntimeError('Refused unexpected API pagination URL')
        try:
            with urlopen(Request(url, headers=headers), timeout=20) as response:
                value = json.load(response)
                link = response.headers.get('Link', '')
        except (HTTPError, URLError, TimeoutError, ValueError) as error:
            code = error.code if isinstance(error, HTTPError) else 'unavailable'
            raise RuntimeError(f'GitHub API request failed ({code}); previous deployment retained') from None
        if key:
            value = value.get(key) if isinstance(value, dict) else None
            if not isinstance(value, list):
                raise RuntimeError('Unexpected GitHub API list response')
        if isinstance(value, dict):
            return value
        if not isinstance(value, list):
            raise RuntimeError('Unexpected GitHub API response')
        items.extend(value)
        match = re.search(r'<([^>]+)>;\s*rel="next"', link)
        if not match:
            return items
        url = match.group(1)
    raise RuntimeError('GitHub pagination limit reached; snapshot not published')


def pr_state(pr):
    if pr.get('merged_at'):
        return 'Merged'
    if pr.get('state') == 'closed':
        return 'Closed'
    if pr.get('state') != 'open':
        raise ValueError('Unknown PR state')
    return 'Draft' if pr.get('draft') else 'Open'


def review_signal(reviews):
    decisions = {}
    for review in sorted(reviews, key=lambda item: (item.get('submitted_at') or '', item.get('id', 0))):
        user = review.get('user') or {}
        login = user.get('login', '')
        if not login or user.get('type') == 'Bot' or login.endswith('[bot]'):
            continue
        state = review.get('state')
        if state in ('APPROVED', 'CHANGES_REQUESTED', 'DISMISSED'):
            decisions[login] = state
    if 'CHANGES_REQUESTED' in decisions.values():
        return 'Changes requested'
    if 'APPROVED' in decisions.values():
        return 'Approved reviews'
    return 'No decisive human review'


def check_signal(checks, statuses):
    # Status history is newest-first. Only the newest result per context applies.
    latest = {}
    for status in statuses:
        latest.setdefault(status.get('context'), status.get('state'))
    results = list(latest.values())
    for check in checks:
        results.append(check.get('conclusion') if check.get('status') == 'completed' else 'pending')
    if not results:
        return 'Not reported'
    if any(value in ('failure', 'error', 'timed_out', 'cancelled', 'startup_failure', 'stale') for value in results):
        return 'Failure'
    if 'action_required' in results:
        return 'Action required'
    if 'pending' in results:
        return 'Pending'
    if any(value not in ('success', 'neutral', 'skipped') for value in results):
        return 'Unknown'
    if all(value in ('neutral', 'skipped') for value in results):
        return 'Neutral / skipped'
    return 'Reported checks passed'


def collect_pr(entry):
    base = '/repos/' + entry['repository']
    pr = api(f"{base}/pulls/{entry['number']}")
    if not isinstance(pr, dict) or not isinstance(pr.get('title'), str):
        raise ValueError('Malformed PR metadata')
    sha = pr.get('head', {}).get('sha')
    if not isinstance(sha, str) or not re.fullmatch('[a-zA-Z0-9]+', sha):
        raise ValueError('Malformed PR head SHA')
    reviews = api(f"{base}/pulls/{entry['number']}/reviews")
    checks = api(f'{base}/commits/{sha}/check-runs', key='check_runs')
    statuses = api(f'{base}/commits/{sha}/statuses')
    if not all(isinstance(value, list) for value in (reviews, checks, statuses)):
        raise ValueError('Malformed PR signals')
    return {'repository': entry['repository'], 'number': entry['number'],
            'title': pr['title'], 'state': pr_state(pr),
            'url': f"https://github.com/{entry['repository']}/pull/{entry['number']}",
            'review': review_signal(reviews), 'checks': check_signal(checks, statuses),
            'updatedAt': pr.get('updated_at'), 'headSha': sha}


def update(entries, destination):
    rows = [collect_pr(entry) for entry in validate_watchlist(entries)]
    payload = {'generatedAt': datetime.now(timezone.utc).isoformat(), 'prs': rows}
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=destination.parent,
                                         suffix='.tmp', delete=False) as handle:
            name = handle.name
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write('\n')
        os.replace(name, destination)
    finally:
        if name and Path(name).exists():
            Path(name).unlink()
    return len(rows)


def main():
    try:
        entries = json.loads((ROOT / 'watchlist.json').read_text(encoding='utf-8'))
        count = update(entries, ROOT / 'site/data.json')
        print(f'Updated complete snapshot: {count} pull requests')
        return 0
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as error:
        # Print no API payloads, credentials or raw network exceptions.
        print(f'Snapshot refresh failed ({type(error).__name__}); no snapshot published.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
