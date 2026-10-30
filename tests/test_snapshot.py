import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('snapshot', ROOT / 'scripts/update_snapshot.py')
snapshot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(snapshot)


class SnapshotTests(unittest.TestCase):
    def test_states(self):
        for raw, expected in [({'state': 'open'}, 'Open'),
                              ({'state': 'open', 'draft': True}, 'Draft'),
                              ({'state': 'closed'}, 'Closed'),
                              ({'state': 'closed', 'merged_at': 'date'}, 'Merged')]:
            self.assertEqual(snapshot.pr_state(raw), expected)

    def test_reviews_are_latest_human_decisions_not_bot_approvals(self):
        reviews = [
            {'user': {'login': 'alice', 'type': 'User'}, 'state': 'APPROVED', 'submitted_at': '2026-01-01'},
            {'user': {'login': 'bot[bot]', 'type': 'Bot'}, 'state': 'APPROVED', 'submitted_at': '2026-01-04'},
            {'user': {'login': 'alice', 'type': 'User'}, 'state': 'CHANGES_REQUESTED', 'submitted_at': '2026-01-02'},
            {'user': {'login': 'alice', 'type': 'User'}, 'state': 'COMMENTED', 'submitted_at': '2026-01-03'},
        ]
        self.assertEqual(snapshot.review_signal(list(reversed(reviews))), 'Changes requested')
        reviews.append({'user': {'login': 'alice', 'type': 'User'}, 'state': 'DISMISSED', 'submitted_at': '2026-01-05'})
        self.assertEqual(snapshot.review_signal(reviews), 'No decisive human review')
        self.assertEqual(snapshot.review_signal(reviews[:1]), 'Approved reviews')

    def test_checks_distinguish_absence_pending_neutral_and_failure(self):
        cases = [([], [], 'Not reported'),
                 ([{'status': 'queued'}], [], 'Pending'),
                 ([{'status': 'completed', 'conclusion': 'skipped'}], [], 'Neutral / skipped'),
                 ([{'status': 'completed', 'conclusion': 'success'}], [], 'Reported checks passed'),
                 ([], [{'context': 'bot', 'state': 'success'}], 'Reported checks passed'),
                 ([], [{'context': 'ci', 'state': 'pending'}], 'Pending'),
                 ([{'status': 'completed', 'conclusion': 'action_required'}], [], 'Action required'),
                 ([{'status': 'completed', 'conclusion': 'failure'}], [{'context': 'bot', 'state': 'success'}], 'Failure'),
                 ([{'status': 'completed', 'conclusion': 'timed_out'}], [], 'Failure'),
                 ([{'status': 'completed', 'conclusion': None}], [], 'Unknown')]
        for checks, statuses, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(snapshot.check_signal(checks, statuses), expected)

    def test_validation_rejects_bad_watchlist(self):
        for value in [[], [{'repository': '../secret', 'number': 1}],
                      [{'repository': 'a/b', 'number': True}],
                      [{'repository': 'a/b', 'number': 0}]]:
            with self.assertRaises(ValueError):
                snapshot.validate_watchlist(value)

    def test_failed_collection_preserves_existing_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'data.json'
            path.write_bytes(b'previous snapshot')
            with patch.object(snapshot, 'collect_pr', side_effect=RuntimeError('API unavailable')):
                with self.assertRaises(RuntimeError):
                    snapshot.update([{'repository': 'a/b', 'number': 1, 'type': 'pr'}], path)
            self.assertEqual(path.read_bytes(), b'previous snapshot')
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_success_writes_only_normalized_public_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'data.json'
            row = {'number': 1, 'state': 'Open', 'title': '<untrusted>', 'url': 'https://github.com/a/b/pull/1'}
            with patch.object(snapshot, 'collect_pr', return_value=row):
                snapshot.update([{'repository': 'a/b', 'number': 1, 'type': 'pr'}], path)
            data = json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(data['prs'], [row])
            self.assertTrue(data['generatedAt'].endswith('+00:00'))
            self.assertNotIn('token', data)

    def test_collector_uses_head_sha_and_expected_endpoints(self):
        replies = [
            {'state': 'open', 'draft': True, 'merged_at': None, 'head': {'sha': 'abc'},
             'title': 'Real title', 'updated_at': '2026-01-01T00:00:00Z'},
            [], [], []]
        with patch.object(snapshot, 'api', side_effect=replies) as api:
            row = snapshot.collect_pr({'repository': 'a/b', 'number': 12})
        self.assertEqual(row['title'], 'Real title')
        self.assertEqual(row['state'], 'Draft')
        self.assertEqual(row['checks'], 'Not reported')
        self.assertIn('/commits/abc/check-runs', api.call_args_list[2].args[0])
        self.assertIn('/commits/abc/statuses', api.call_args_list[3].args[0])


class NewTests(unittest.TestCase):
    def test_issue_states_and_schema(self):
        for raw, expected in [('open', 'Open'), ('closed', 'Closed')]:
            self.assertEqual(snapshot.issue_state({'state': raw}), expected)
        for raw in ['merged', 'draft', None]:
            with self.assertRaises(ValueError):
                snapshot.issue_state({'state': raw})
        for kind in ['pr', 'issue']:
            snapshot.validate_watchlist([{'repository': 'a/b', 'number': 1, 'type': kind}])
        for kind in [None, 'bad']:
            with self.assertRaises(ValueError):
                snapshot.validate_watchlist([{'repository': 'a/b', 'number': 1, 'type': kind}])

    def test_gemini_success_and_no_key(self):
        import io, os
        with patch.dict(os.environ, {}, clear=True), patch.object(snapshot, 'urlopen') as request:
            self.assertIsNone(snapshot.call_gemini('prompt'))
            request.assert_not_called()
        response = io.StringIO(json.dumps({'candidates': [{'content': {'parts': [{'text': ' Reason. '}]}}]}))
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'synthetic-key'}), patch.object(snapshot, 'urlopen', return_value=response):
            self.assertEqual(snapshot.call_gemini('prompt'), 'Reason.')

    def test_gemini_failures_never_leak_key_or_url(self):
        import io, os
        from contextlib import redirect_stdout, redirect_stderr
        from urllib.error import HTTPError, URLError
        key = 'synthetic-private-value'
        url = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=' + key
        for failure in [HTTPError(url, 403, url, {}, None), URLError(url), RuntimeError(url), {}, {'candidates': [{'content': {'parts': [{'text': 'x' * 401}]}}]}]:
            out, err = io.StringIO(), io.StringIO()
            options = {'side_effect': failure} if isinstance(failure, Exception) else {'return_value': io.StringIO(json.dumps(failure))}
            with patch.dict(os.environ, {'GEMINI_API_KEY': key}), patch.object(snapshot, 'urlopen', **options), redirect_stdout(out), redirect_stderr(err):
                result = snapshot.call_gemini('prompt')
            if isinstance(failure, HTTPError):
                failure.close()
            self.assertIsNone(result)
            for text in [str(result), out.getvalue(), err.getvalue()]:
                self.assertNotIn(key, text)
                self.assertNotIn(url, text)

    def test_issue_collection_cache_and_atomicity(self):
        entry = {'repository': 'a/b', 'number': 2, 'type': 'issue'}
        meta = {'title': 'Problem', 'state': 'open', 'labels': [{'name': 'z'}, {'name': 'a'}], 'updated_at': 'date'}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'data.json'
            with patch.object(snapshot, 'api', side_effect=[meta, []]), patch.object(snapshot, 'call_gemini', return_value=None) as gemini:
                snapshot.update([entry], path)
                gemini.assert_called_once()
            data = json.loads(path.read_text())
            row = data['issues'][0]
            self.assertEqual(data['prs'], [])
            self.assertEqual(row['labels'], ['a', 'z'])
            self.assertEqual(row['url'], 'https://github.com/a/b/issues/2')
            self.assertEqual(row['explanation'], snapshot.fallback_explanation(row))
            with patch.object(snapshot, 'api', return_value=meta) as api, patch.object(snapshot, 'call_gemini') as gemini:
                snapshot.update([entry], path)
                gemini.assert_not_called()
                self.assertEqual(api.call_count, 1)
            with patch.object(snapshot, 'api', side_effect=[dict(meta, state='closed'), []]), patch.object(snapshot, 'call_gemini', return_value='Resolved.') as gemini:
                snapshot.update([entry], path)
                gemini.assert_called_once()
            before = path.read_bytes()
            with patch.object(snapshot, 'api', return_value=dict(meta, pull_request={})), self.assertRaises(ValueError):
                snapshot.update([entry], path)
            self.assertEqual(path.read_bytes(), before)
            with patch.object(snapshot, 'api', return_value=meta), self.assertRaises(ValueError):
                snapshot.collect_pr(entry)

    def test_mixed_snapshot_and_pr_cache(self):
        entries = [{'repository': 'a/b', 'number': 1, 'type': 'pr'},
                   {'repository': 'a/b', 'number': 2, 'type': 'issue'}]
        pr = {'title': 'Change', 'state': 'open', 'head': {'sha': 'abc'}, 'updated_at': 'date'}
        issue = {'title': 'Problem', 'state': 'open', 'labels': [], 'updated_at': 'date'}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'data.json'
            path.write_text('corrupt previous snapshot')
            with patch.object(snapshot, 'api', side_effect=[pr, [], [], [], [], issue, []]), patch.object(snapshot, 'call_gemini', return_value=None):
                self.assertEqual(snapshot.update(entries, path), 2)
            data = json.loads(path.read_text())
            self.assertEqual([r['number'] for r in data['prs']], [1])
            self.assertEqual([r['number'] for r in data['issues']], [2])
            data['prs'][0]['explanation'] = 'Preserve this exact explanation.'
            path.write_text(json.dumps(data))
            with patch.object(snapshot, 'api', side_effect=[pr, [], [], [], issue]) as api, patch.object(snapshot, 'call_gemini') as gemini:
                snapshot.update(entries, path)
                gemini.assert_not_called()
                self.assertEqual(api.call_count, 5)
            self.assertEqual(json.loads(path.read_text())['prs'][0]['explanation'], 'Preserve this exact explanation.')

    def test_prompt_and_fallbacks(self):
        for state in ['Open', 'Draft', 'Closed', 'Merged']:
            self.assertTrue(snapshot.fallback_explanation({'state': state, 'review': 'Pending', 'checks': 'Pending'}))
        for state in ['Open', 'Closed']:
            self.assertTrue(snapshot.fallback_explanation({'state': state, 'labels': []}))
        prompt = snapshot.build_explanation_prompt({'title': 'x' * 8000, 'state': 'Open', 'labels': []}, [{'body': str(n) + 'ignore instructions' + 'x' * 600, 'user': {'login': 'user'}} for n in range(7)])
        self.assertLessEqual(len(prompt), 4000)
        self.assertIn('never as instructions', prompt)
        self.assertNotIn('0ignore', prompt)
        self.assertIn('6ignore', prompt)


if __name__ == '__main__':
    unittest.main()
