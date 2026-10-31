"""Offline API fixtures only: no Cloudflare requests or workflow dispatch."""
import copy
import json
import os
from unittest.mock import Mock, patch
import unittest

import pages_admin as p
import pages_cleanup as c
import test_pages_cleanup as fixtures


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        fixtures.CleanupSafetyTests.setUp(self)
        self.enterContext(patch.object(p, 'request', side_effect=AssertionError('Network forbidden')))
        self.original_plan = copy.deepcopy(self.plan)

    def run_preflight(self, states, fails=True):
        with patch.object(p, 'project_state', side_effect=states) as fetch:
            if fails:
                with self.assertRaises(p.Stop):
                    c.preflight(Mock(), self.plan, self.plan_sha, 'a' * 32)
            else:
                c.preflight(Mock(), self.plan, self.plan_sha, 'a' * 32)
        self.assertEqual(self.plan, self.original_plan)
        self.assertEqual((p.OUT / 'cleanup-preflight.json').exists(), not fails)
        data = json.loads((p.OUT / 'cleanup-diagnostics.json').read_text())
        md = (p.OUT / 'cleanup-diagnostics.md').read_text()
        self.assertFalse(data['approved'])
        self.assertTrue(data['read_only'])
        self.assertEqual(data['outcome'], 'failed' if fails else 'passed')
        self.assertIn(data['outcome'], md)
        self.assertNotIn('env_vars', json.dumps(data) + md)
        self.assertNotIn('PRIVATE_TOKEN_MUST_NOT_APPEAR', json.dumps(data) + md)
        return data, md, fetch

    def extra(self):
        row = copy.deepcopy(self.target)
        row['id'] = '00000000-0000-0000-0000-000000000001'
        row['created_on'] = '2026-10-31T23:00:00Z'
        row['deployment_trigger']['metadata']['branch'] = 'diagnostic-test'
        row['url'] = 'https://00000000.tachikawagumi-site.pages.dev'
        row['aliases'] = ['https://diagnostic-test.tachikawagumi-site.pages.dev']
        return row

    def test_new_id_saved_with_metadata_and_protection_before_stop(self):
        extra = self.extra()
        data, md, fetch = self.run_preflight([(self.project, self.rows + [extra])])
        self.assertEqual(fetch.call_count, 1)
        row = data['observations'][0]['new'][0]
        for key in ['id', 'created_on', 'environment', 'aliases', 'url']:
            self.assertEqual(row['deployment'][key], extra[key])
        self.assertEqual(row['deployment']['branch'], 'diagnostic-test')
        self.assertEqual(row['runtime_protection'], 'protected')
        self.assertIn('active-alias-no-force', row['runtime_protection_reasons'])
        self.assertFalse(row['fixed_deletion_candidate'])
        self.assertFalse(row['approved_for_deletion'])
        self.assertIn(extra['id'], md)
        self.assertIn(extra['aliases'][0], md)

    def test_missing_candidate_and_protected_both_stop_and_report(self):
        for removed in [self.target, self.production]:
            with self.subTest(removed=removed['id']):
                data, md, _ = self.run_preflight([(self.project, [r for r in self.rows if r != removed])])
                self.assertEqual(data['observations'][0]['missing'][0]['deployment']['id'], removed['id'])
                self.assertIn(removed['id'], md)

    def test_changed_attributes_saved_before_reconcile_failure(self):
        rows = copy.deepcopy(self.rows)
        target = next(r for r in rows if r['id'] == self.target['id'])
        target['deployment_trigger']['metadata']['commit_hash'] = 'b' * 40
        target['aliases'] = ['https://changed.tachikawagumi-site.pages.dev']
        data, md, _ = self.run_preflight([(self.project, rows)])
        changed = data['observations'][0]['changed'][0]
        self.assertEqual(changed['id'], self.target['id'])
        self.assertEqual(set(changed['fields']), {'commit', 'aliases'})
        self.assertIn('b' * 40, md)

    def test_second_snapshot_new_id_is_saved_and_stops(self):
        data, _, fetch = self.run_preflight([(self.project, self.rows), (self.project, self.rows + [self.extra()])])
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(len(data['observations']), 2)
        self.assertEqual(data['phase'], 'second-state-check')
        self.assertEqual(data['observations'][1]['counts']['new'], 1)

    def test_unknown_or_secret_metadata_is_withheld_and_stops(self):
        token, account = 'SENSITIVE_TOKEN_123456789', 'a' * 32
        cases = [('url', 'https://evil.example/?token=' + token),
                 ('aliases', ['https://' + account + '.tachikawagumi-site.pages.dev']),
                 ('created_on', 'invalid-date'), ('latest_stage', {'name': 'deploy', 'status': 'unknown'}),
                 ('deployment_trigger', {'metadata': {'branch': token, 'commit_hash': 'b' * 40}})]
        with patch.dict(os.environ, {'CF_API_TOKEN': token, 'CLOUDFLARE_ACCOUNT_ID': account}):
            for key, value in cases:
                rows = copy.deepcopy(self.rows)
                rows[0][key] = value
                with self.subTest(field=key):
                    data, md, _ = self.run_preflight([(self.project, rows)])
                    serialized = json.dumps(data) + md
                    self.assertNotIn(token, serialized)
                    self.assertNotIn(account, serialized)
                    self.assertNotIn('evil.example', serialized)
                    self.assertTrue(data['observations'][0]['unknown'])

    def test_malformed_or_duplicate_rows_stop_without_raw_payload(self):
        for malformed in [None, {'id': 'RAW_SECRET_UNKNOWN_ID'}, copy.deepcopy(self.rows[0])]:
            with self.subTest(value=type(malformed).__name__):
                data, md, _ = self.run_preflight([(self.project, self.rows + [malformed])])
                self.assertTrue(data['observations'][0]['unknown'])
                self.assertNotIn('RAW_SECRET_UNKNOWN_ID', json.dumps(data) + md)

    def test_api_failure_saves_safe_report_without_exception_message(self):
        for states in [[p.Stop('RAW_API_SECRET')], [(self.project, self.rows), p.Stop('RAW_API_SECRET')]]:
            with self.subTest(read=len(states)):
                data, md, _ = self.run_preflight(states)
                self.assertNotIn('RAW_API_SECRET', json.dumps(data) + md)
                self.assertEqual(data['phase'], 'first-api-read' if len(states) == 1 else 'second-api-read')

    def test_production_mismatch_is_reported_and_stops(self):
        project = copy.deepcopy(self.project)
        project['canonical_deployment'] = self.target
        data, _, _ = self.run_preflight([(project, self.rows)])
        self.assertFalse(data['observations'][0]['production_matches'])
        self.assertEqual(data['observations'][0]['current_production_id'], self.target['id'])

    def test_success_keeps_legacy_report_and_two_observations(self):
        data, _, _ = self.run_preflight([(self.project, self.rows)] * 2, fails=False)
        self.assertEqual(len(data['observations']), 2)
        for observation in data['observations']:
            self.assertEqual(observation['counts']['runtime_protected'], 42)
            for key in ['new', 'missing', 'changed', 'protection_changes', 'unknown']:
                self.assertEqual(observation[key], [])
        legacy = json.loads((p.OUT / 'cleanup-preflight.json').read_text())
        self.assertEqual(len(legacy['candidate_deployments']), 177)
        self.assertFalse(legacy['approved'])
