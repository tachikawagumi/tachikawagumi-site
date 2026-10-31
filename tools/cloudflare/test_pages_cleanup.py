import copy
import datetime as dt
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import pages_admin as p
import pages_cleanup as c


def raw_deployment(row):
    return {"id": row["id"], "url": row["url"], "aliases": row["aliases"],
            "environment": row["environment"], "created_on": row["created_on"],
            "deployment_trigger": {"metadata": {"branch": row["branch"], "commit_hash": row["commit"]}},
            "latest_stage": {"name": row["stage"], "status": row["status"]},
            "env_vars": {"NEVER_LOG": {"value": "PRIVATE_TOKEN_MUST_NOT_APPEAR"}}}


class CleanupSafetyTests(unittest.TestCase):
    def setUp(self):
        output = tempfile.TemporaryDirectory()
        self.addCleanup(output.cleanup)
        self.enterContext(patch.object(p, "OUT", Path(output.name)))
        self.stdout = patch("sys.stdout", new_callable=io.StringIO)
        self.stdout.start()
        self.addCleanup(self.stdout.stop)
        self.plan, self.plan_sha = c.load_plan()
        self.rows = [raw_deployment(r) for r in self.plan["deployments"]]
        self.target = next(r for r in self.rows if r["id"] == self.plan["candidate_ids"][0])
        self.production = next(r for r in self.rows if r["id"] == c.PRODUCTION)
        self.project = {"name": c.PROJECT, "subdomain": c.SUBDOMAIN, "canonical_deployment": self.production,
                        "domains": ["tachikawagumi.co.jp"], "source": {"type": "github", "config": {
                            "owner": "tachikawagumi", "repo_name": "tachikawagumi-site"}}}
        now = dt.datetime.now(dt.timezone.utc)
        self.approval = {"schema_version": 1, "enabled": True, "project_name": c.PROJECT,
                         "plan_sha256": self.plan_sha, "account_sha256": c.sha(("a" * 32).encode()),
                         "state_sha256": c.state_hash(self.plan, set()), "preflight_run_id": "123",
                         "authorized_ids": [self.target["id"]], "expected_absent_ids": [], "max_deletions": 1,
                         "approved_by": "tachikawagumi", "approval_record": "TEST-ONLY MOCK APPROVAL",
                         "approved_at": (now - dt.timedelta(minutes=1)).isoformat(),
                         "expires_at": (now + dt.timedelta(hours=1)).isoformat()}

    def approval_context(self, value):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / "approval.json"
        path.write_text(json.dumps(value))
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        self.enterContext(patch.object(c, "APPROVAL_PATH", path))
        self.enterContext(patch.dict(os.environ, {"APPROVAL_SHA256": sha, "GITHUB_ACTOR": "tachikawagumi",
            "GITHUB_TRIGGERING_ACTOR": "tachikawagumi", "CF_PAGES_DELETE_ENABLED": "true",
            "CONFIRMATION": f"DELETE:{sha}:{len(value['authorized_ids'])}"}))
        return sha

    def assert_no_delete(self, api):
        self.assertFalse(any(call.kwargs.get("method") == "DELETE" for call in api.call.call_args_list))

    def test_frozen_plan_counts_and_both_explicit_protections(self):
        self.assertEqual(len(self.plan["candidate_ids"]), 177)
        self.assertEqual(len(self.plan["deployments"]), 219)
        self.assertFalse(c.NEVER_DELETE.intersection(self.plan["candidate_ids"]))
        self.assertNotIn(c.TRIAL_DELETED, [d["id"] for d in self.plan["deployments"]])
        self.assertEqual(c.reconcile(self.project, self.rows, self.plan), set())

    def test_disabled_committed_approval_cannot_execute(self):
        self.assertFalse(json.loads(c.APPROVAL_PATH.read_text())["enabled"])
        self.assertEqual(json.loads(c.APPROVAL_PATH.read_text())["authorized_ids"], [])
        with self.assertRaises(p.Stop):
            c.load_approval(self.plan, self.plan_sha, "a" * 32)

    def test_preflight_only_gets_no_probe_no_delete_and_no_secret_report(self):
        api = Mock()
        with patch.object(p, "project_state", return_value=(self.project, self.rows)), patch.object(
                p, "write_report") as report, patch.object(p, "probe") as probe:
            c.preflight(api, self.plan, self.plan_sha, "a" * 32)
        api.call.assert_not_called()
        probe.assert_not_called()
        data = report.call_args.args[1]
        self.assertEqual(len(data["candidate_deployments"]), 177)
        self.assertEqual(len(data["protected_deployments"]), 42)
        self.assertFalse(data["approved"])
        self.assertNotIn("PRIVATE_TOKEN", json.dumps(data))
        self.assertNotIn("env_vars", json.dumps(data))
        self.assertNotIn("a" * 32, json.dumps(data))

    def test_production_change_blocks(self):
        project = copy.deepcopy(self.project)
        project["canonical_deployment"] = self.target
        with self.assertRaises(p.Stop):
            c.reconcile(project, self.rows, self.plan)

    def test_alias_branch_url_commit_status_and_timestamp_changes_block(self):
        for key, value in [("aliases", ["https://new.tachikawagumi-site.pages.dev"]),
                           ("url", "https://evil.example"), ("created_on", "2026-10-31T23:00:00Z")]:
            rows = copy.deepcopy(self.rows)
            rows[0][key] = value
            with self.subTest(key=key), self.assertRaises(p.Stop):
                c.reconcile(self.project, rows, self.plan)
        for key, value in [("branch", "other"), ("commit_hash", "b" * 40)]:
            rows = copy.deepcopy(self.rows)
            rows[0]["deployment_trigger"]["metadata"][key] = value
            with self.subTest(key=key), self.assertRaises(p.Stop):
                c.reconcile(self.project, rows, self.plan)
        rows = copy.deepcopy(self.rows)
        rows[0]["latest_stage"]["status"] = "active"
        with self.assertRaises(p.Stop):
            c.reconcile(self.project, rows, self.plan)

    def test_new_deployment_never_auto_added(self):
        extra = copy.deepcopy(self.target)
        extra["id"] = "00000000-0000-0000-0000-000000000001"
        with self.assertRaises(p.Stop):
            c.reconcile(self.project, self.rows + [extra], self.plan)

    def test_missing_candidate_is_reported_not_assumed_closed(self):
        rows = [r for r in self.rows if r["id"] != self.target["id"]]
        self.assertEqual(c.reconcile(self.project, rows, self.plan), {self.target["id"]})
        with self.assertRaises(p.Stop):
            c.reconcile(self.project, rows, self.plan, set())

    def test_missing_protected_id_blocks(self):
        rows = [r for r in self.rows if r["id"] != "a0244d88-1233-478b-8c1d-cc031c227862"]
        with self.assertRaises(p.Stop):
            c.reconcile(self.project, rows, self.plan)

    def test_preflight_race_is_not_usable(self):
        with patch.object(p, "project_state", side_effect=[(self.project, self.rows),
                (self.project, self.rows[1:])]), patch.object(p, "write_report") as report, self.assertRaises(p.Stop):
            c.preflight(Mock(), self.plan, self.plan_sha, "a" * 32)
        self.assertTrue(report.called)
        self.assertTrue(all(call.args[0] == "cleanup-diagnostics.json" for call in report.call_args_list))
        self.assertEqual(report.call_args.args[1]["outcome"], "failed")

    def test_valid_bounded_representative_approval(self):
        self.approval_context(self.approval)
        actual, _ = c.load_approval(self.plan, self.plan_sha, "a" * 32)
        self.assertEqual(actual, self.approval)

    def test_wrong_account_digest_actor_confirmation_enable_refused(self):
        self.approval_context(self.approval)
        for key, value in [("APPROVAL_SHA256", "wrong"), ("GITHUB_ACTOR", "other"),
                           ("GITHUB_TRIGGERING_ACTOR", "other"), ("CF_PAGES_DELETE_ENABLED", "false"),
                           ("CONFIRMATION", "DELETE:ALL")]:
            with self.subTest(key=key), patch.dict(os.environ, {key: value}), self.assertRaises(p.Stop):
                c.load_approval(self.plan, self.plan_sha, "a" * 32)
        with self.assertRaises(p.Stop):
            c.load_approval(self.plan, self.plan_sha, "b" * 32)

    def test_expired_or_overlong_or_future_approval_refused(self):
        for key, value in [("expires_at", "2020-01-01T00:00:00Z"),
                           ("expires_at", "2099-01-01T00:00:00Z"),
                           ("approved_at", "2099-01-01T00:00:00Z")]:
            approval = {**self.approval, key: value}
            self.approval_context(approval)
            with self.subTest(key=key), self.assertRaisesRegex(p.Stop, "Approval expired/invalid"):
                c.load_approval(self.plan, self.plan_sha, "a" * 32)

    def test_protected_duplicate_unbounded_or_empty_selection_refused(self):
        for ids in [[c.PRODUCTION], ["a0244d88-1233-478b-8c1d-cc031c227862"], [c.TRIAL_DELETED],
                    [self.target["id"]] * 2, self.plan["candidate_ids"][:26], []]:
            approval = {**self.approval, "authorized_ids": ids, "max_deletions": len(ids)}
            self.approval_context(approval)
            with self.subTest(ids=ids[:2]), self.assertRaises(p.Stop):
                c.load_approval(self.plan, self.plan_sha, "a" * 32)

    def test_preflight_hash_or_count_mismatch_refused(self):
        for key, value in [("state_sha256", "wrong"), ("plan_sha256", "wrong"), ("max_deletions", 2),
                           ("preflight_run_id", None), ("approval_record", "")]:
            approval = {**self.approval, key: value}
            self.approval_context(approval)
            with self.subTest(key=key), self.assertRaises(p.Stop):
                c.load_approval(self.plan, self.plan_sha, "a" * 32)

    def test_scoped_api_denies_other_projects_access_config_force_and_unapproved_id(self):
        api = c.ScopedAPI("test", "a" * 32, [self.target["id"]])
        bad = [("/pages/projects/palkari/deployments", "GET"), ("/pages/projects", "GET"),
               (f"/pages/projects/{c.PROJECT}", "PATCH"), ("/access/apps", "GET"),
               (f"/pages/projects/{c.PROJECT}/deployments/{c.PRODUCTION}", "DELETE"),
               (f"/pages/projects/{c.PROJECT}/deployments/{self.target['id']}?force=true", "DELETE"),
               (f"/pages/projects/{c.PROJECT}", "DELETE")]
        with patch.object(p.API, "call") as call:
            for route, method in bad:
                with self.subTest(route=route), self.assertRaises(p.Stop):
                    api.call(route, method)
            call.assert_not_called()

    def test_trusted_main_rejects_push_pr_branch_stale_or_unverifiable(self):
        env = {"GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF": "refs/heads/main",
               "GITHUB_REPOSITORY": c.REPOSITORY, "GITHUB_SHA": "a" * 40}
        with patch.dict(os.environ, env), patch.object(c.subprocess, "run", return_value=Mock(
                returncode=0, stdout="a" * 40 + "\trefs/heads/main\n")) as run:
            c.trusted_main()
            run.assert_called_once()
            for key, value in [("GITHUB_EVENT_NAME", "push"), ("GITHUB_REF", "refs/heads/feature"),
                               ("GITHUB_REPOSITORY", "other/repository"), ("GITHUB_SHA", "b" * 40)]:
                with patch.dict(os.environ, {key: value}), self.assertRaises(p.Stop):
                    c.trusted_main()

    def run_batch(self, *, rows=None, closed=True, api_error=False, health_error=False):
        api = Mock()
        api.call.side_effect = [{"result": self.target}, p.Stop("API outcome unconfirmed") if api_error else {"success": True}]
        remaining = [r for r in self.rows if r["id"] != self.target["id"]]
        states = [(self.project, self.rows), (self.project, rows if rows is not None else self.rows),
                  (self.project, remaining)]
        with patch.object(c, "trusted_main"), patch.object(p, "project_state", side_effect=states), patch.object(
                p, "production_health", side_effect=p.Stop("Health failed") if health_error else None,
                return_value={"ok": True}), patch.object(c, "verify_closed", return_value=([], closed)), patch.object(
                p, "write_report") as report:
            try:
                c.delete_batch(api, self.plan, self.approval, "hash", lambda: (self.approval, "hash"))
                error = None
            except p.Stop as exc:
                error = exc
            return api, report, error

    def test_one_exact_delete_no_force_verified_completion(self):
        api, report, error = self.run_batch()
        self.assertIsNone(error)
        deletes = [call for call in api.call.call_args_list if call.kwargs.get("method") == "DELETE"]
        self.assertEqual(len(deletes), 1)
        self.assertEqual(deletes[0].args[0], f"/pages/projects/{c.PROJECT}/deployments/{self.target['id']}")
        self.assertTrue(report.call_args.args[1]["complete"])

    def test_immediate_race_blocks_before_delete(self):
        rows = copy.deepcopy(self.rows)
        rows[0]["aliases"] = ["https://changed.tachikawagumi-site.pages.dev"]
        api, _, error = self.run_batch(rows=rows)
        self.assertIsNotNone(error)
        self.assert_no_delete(api)

    def test_production_health_failure_blocks_before_delete(self):
        api, _, error = self.run_batch(health_error=True)
        self.assertIsNotNone(error)
        self.assert_no_delete(api)

    def test_timeout_records_unconfirmed_and_never_retries(self):
        api, report, error = self.run_batch(api_error=True)
        self.assertIsNotNone(error)
        self.assertEqual(sum(call.kwargs.get("method") == "DELETE" for call in api.call.call_args_list), 1)
        self.assertEqual(report.call_args.args[1]["attempts"][0]["api_outcome"], "unconfirmed")
        self.assertFalse(report.call_args.args[1]["complete"])

    def test_image_or_root_not_closed_stops_before_next_id(self):
        self.approval["authorized_ids"].append(self.plan["candidate_ids"][1])
        api, report, error = self.run_batch(closed=False)
        self.assertIsNotNone(error)
        self.assertEqual(sum(call.kwargs.get("method") == "DELETE" for call in api.call.call_args_list), 1)
        self.assertFalse(report.call_args.args[1]["complete"])

    def test_closure_requires_all_nine_images_and_root_404_or_410(self):
        for status in [200, 302, 403, 0]:
            checks = [{"result": "not-found", "http": 404} for _ in p.PATHS]
            with patch.object(p, "inspect_urls", return_value=(checks, [])), patch.object(p, "probe", return_value={
                    "result": "unknown", "http": status}):
                _, closed = c.verify_closed(self.target)
                self.assertFalse(closed)

    def test_two_deletions_are_serial_and_use_expected_remaining_membership(self):
        targets = [next(r for r in self.rows if r["id"] == id_) for id_ in self.plan["candidate_ids"][:2]]
        approval = {**self.approval, "authorized_ids": [t["id"] for t in targets], "max_deletions": 2}
        removed_one = [r for r in self.rows if r["id"] != targets[0]["id"]]
        removed_both = [r for r in removed_one if r["id"] != targets[1]["id"]]
        api = Mock()
        api.call.side_effect = [{"result": targets[0]}, {"success": True}, {"result": targets[1]}, {"success": True}]
        states = [(self.project, self.rows)] * 2 + [(self.project, removed_one)] * 3 + [(self.project, removed_both)]
        with patch.object(c, "trusted_main"), patch.object(p, "project_state", side_effect=states), patch.object(
                p, "production_health", return_value={"ok": True}) as health, patch.object(
                c, "verify_closed", return_value=([], True)) as closed, patch.object(p, "write_report") as report:
            c.delete_batch(api, self.plan, approval, "hash", lambda: (approval, "hash"))
        self.assertEqual(health.call_count, 4)
        self.assertEqual(closed.call_count, 2)
        self.assertEqual([call.kwargs.get("method", "GET") for call in api.call.call_args_list],
                         ["GET", "DELETE", "GET", "DELETE"])
        self.assertEqual(report.call_args.args[1]["completed_ids"], approval["authorized_ids"])

    def test_api_readback_failure_still_checks_production_and_stops(self):
        api = Mock()
        api.call.side_effect = [{"result": self.target}, {"success": True}]
        with patch.object(c, "trusted_main"), patch.object(p, "project_state", side_effect=[
                (self.project, self.rows), (self.project, self.rows), p.Stop("Readback failed")]), patch.object(
                p, "production_health", return_value={"ok": True}) as health, patch.object(
                p, "write_report") as report, self.assertRaises(p.Stop):
            c.delete_batch(api, self.plan, self.approval, "hash", lambda: (self.approval, "hash"))
        self.assertEqual(health.call_count, 2)
        self.assertFalse(report.call_args.args[1]["complete"])
        self.assertEqual(report.call_args.args[1]["attempts"][0]["api_outcome"], "accepted")

    def test_approval_expiring_during_health_check_prevents_delete(self):
        api = Mock()
        validation = Mock(side_effect=[(self.approval, "hash"), p.Stop("Approval expired/invalid")])
        with patch.object(c, "trusted_main"), patch.object(p, "project_state", return_value=(self.project, self.rows)), patch.object(
                p, "production_health", return_value={"ok": True}), patch.object(
                p, "write_report"), self.assertRaises(p.Stop):
            c.delete_batch(api, self.plan, self.approval, "hash", validation)
        api.call.assert_not_called()

    def test_scoped_api_allows_only_approved_exact_delete_without_force(self):
        api = c.ScopedAPI("test", "a" * 32, [self.target["id"]])
        route = f"/pages/projects/{c.PROJECT}/deployments/{self.target['id']}"
        with patch.object(p.API, "call", return_value={"success": True}) as call:
            api.call(route, "DELETE")
            call.assert_called_once_with(route, "DELETE")

    def test_actual_project_state_pagination_uses_only_scoped_gets(self):
        api = c.ScopedAPI("test", "a" * 32)
        responses = [{"success": True, "result": self.project}] + [
            {"success": True, "result": self.rows[n:n+10], "result_info": {"total_count": len(self.rows)}}
            for n in range(0, len(self.rows), 10)]
        with patch.object(p, "request", side_effect=[(200, {}, json.dumps(r).encode()) for r in responses]) as request:
            project, rows = p.project_state(api, c.PROJECT)
        self.assertEqual(c.reconcile(project, rows, self.plan), set())
        self.assertEqual(request.call_count, 23)
        self.assertTrue(all(call.args[2] == "GET" for call in request.call_args_list))
        self.assertTrue(all("/pages/projects/" + c.PROJECT in call.args[0] for call in request.call_args_list))


if __name__ == "__main__":
    unittest.main()
