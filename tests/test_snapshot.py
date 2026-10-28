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
                    snapshot.update([{'repository': 'a/b', 'number': 1}], path)
            self.assertEqual(path.read_bytes(), b'previous snapshot')
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_success_writes_only_normalized_public_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'data.json'
            row = {'number': 1, 'state': 'Open', 'title': '<untrusted>', 'url': 'https://github.com/a/b/pull/1'}
            with patch.object(snapshot, 'collect_pr', return_value=row):
                snapshot.update([{'repository': 'a/b', 'number': 1}], path)
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


if __name__ == '__main__':
    unittest.main()
