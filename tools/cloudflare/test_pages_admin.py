import copy
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

import pages_admin as p


def deployment(number, date, branch="old", aliases=None):
    return {"id": f"00000000-0000-0000-0000-{number:012d}", "created_on": date,
            "url": f"https://d{number}.example.pages.dev", "aliases": aliases or [],
            "environment": "preview", "latest_stage": {"name": "deploy", "status": "success"},
            "deployment_trigger": {"metadata": {"branch": branch, "commit_hash": "a" * 40}},
            "env_vars": {"SECRET": {"value": "NEVER_PRINT_THIS"}}}


class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.old = deployment(1, "2026-10-01T00:00:00Z")
        self.latest = deployment(2, "2026-10-02T00:00:00Z")
        self.prod = deployment(3, "2026-10-03T00:00:00Z", "main")
        self.prod["environment"] = "production"
        self.project = {"name": "verified", "canonical_deployment": self.prod,
                        "subdomain": "example.pages.dev", "domains": ["tachikawagumi.co.jp"],
                        "source": {"type": "github", "config": {"owner": "tachikawagumi", "repo_name": "tachikawagumi-site"}}}
        self.deployments = [self.old, self.latest, self.prod]

    def test_current_production_never_candidate(self):
        self.assertIn("current-production", p.protected(self.project, self.deployments, self.prod))

    def test_latest_branch_protected(self):
        self.assertIn("latest-branch", p.protected(self.project, self.deployments, self.latest))

    def test_latest_successful_protected_when_newer_build_failed(self):
        self.latest["latest_stage"]["status"] = "failure"
        self.assertIn("latest-successful-branch", p.protected(self.project, self.deployments, self.old))

    def test_alias_no_force(self):
        self.old["aliases"] = ["https://old.example.pages.dev"]
        self.assertIn("active-alias-no-force", p.protected(self.project, self.deployments, self.old))

    def test_unknown_production_fails_closed(self):
        self.project["canonical_deployment"] = None
        self.assertIn("current-production-unverified", p.protected(self.project, self.deployments, self.old))

    def test_unknown_branch_fails_closed(self):
        self.old["deployment_trigger"] = {}
        self.assertIn("branch-unknown", p.protected(self.project, self.deployments, self.old))

    def test_tied_latest_dates_both_protected(self):
        self.old["created_on"] = self.latest["created_on"]
        self.assertIn("latest-branch", p.protected(self.project, self.deployments, self.old))

    def test_old_unaliased_candidate_not_approval(self):
        self.assertEqual(p.protected(self.project, self.deployments, self.old), [])

    def test_summary_excludes_secrets(self):
        self.assertNotIn("NEVER_PRINT_THIS", json.dumps(p.summary(self.old)))
        self.assertNotIn("env_vars", p.summary(self.old))

    def test_untrusted_url_rejected(self):
        for url in ["https://evil.example/", "https://tachikawagumi.co.jp", "http://x.example.pages.dev",
                    "https://example.pages.dev.evil.test", "https://x.example.pages.dev/?token=SECRET",
                    "https://user:pass@x.example.pages.dev", "https://x.example.pages.dev:443"]:
            with self.subTest(url=url), self.assertRaises(p.Stop):
                p.origin(url, "example.pages.dev")
        self.assertEqual(p.origin("https://x.example.pages.dev/", "example.pages.dev"), "https://x.example.pages.dev")

    def test_pagination_honors_server_page_size(self):
        api = p.API("test", "a" * 32)
        with patch.object(api, "call", side_effect=[
                {"result": [{"id": "1"}], "result_info": {"total_pages": 2, "total_count": 2}},
                {"result": [{"id": "2"}], "result_info": {"total_pages": 2, "total_count": 2}}]) as call:
            self.assertEqual(len(api.all("/pages/projects")), 2)
            self.assertIn("page=2", call.call_args.args[0])

    def test_repeated_page_fails_closed(self):
        api = p.API("test", "a" * 32)
        with patch.object(api, "call", return_value={"result": [{"id": "1"}]}), self.assertRaises(p.Stop):
            api.all("/pages/projects")

    def test_partial_pagination_fails_closed(self):
        api = p.API("test", "a" * 32)
        with patch.object(api, "call", return_value={"result": [{"id": "1"}], "result_info": {"total_pages": 1, "total_count": 2}}), self.assertRaises(p.Stop):
            api.all("/pages/projects")

    def test_gps_tag_detected_without_reading_coordinates(self):
        tiff = b"II" + struct.pack("<HIH", 42, 8, 1) + struct.pack("<HHII", 0x8825, 4, 1, 26) + b"\0" * 4
        exif = b"Exif\0\0" + tiff
        jpeg = b"\xff\xd8\xff\xe1" + (len(exif) + 2).to_bytes(2, "big") + exif + b"\xff\xda"
        self.assertEqual(p.image_metadata(jpeg), (True, True))
        webp_data = b"WEBP" + b"EXIF" + len(exif).to_bytes(4, "little") + exif + (b"\0" if len(exif) % 2 else b"")
        self.assertEqual(p.image_metadata(b"RIFF" + len(webp_data).to_bytes(4, "little") + webp_data), (True, True))

    def test_corrupt_exif_is_unknown_not_safe(self):
        self.assertIsNone(p.gps_ifd(b"broken"))
        self.assertEqual(p.image_metadata(b"<html>login</html>"), (False, None))

    def test_probe_no_credentials_or_redirect_assumption(self):
        with patch.object(p, "request", return_value=(302, {"Location": "https://login.test"}, b"")) as call:
            self.assertEqual(p.probe("https://x.example.pages.dev/a.jpg")["result"], "redirect-unverified")
            self.assertEqual(len(call.call_args.args), 1)

    def test_200_html_not_image(self):
        with patch.object(p, "request", return_value=(200, {}, b"<html>not found</html>")):
            self.assertEqual(p.probe("https://x.example.pages.dev/a.jpg")["result"], "unknown-http-200")

    def test_dry_run_never_deletes(self):
        api = unittest.mock.Mock()
        api.call.return_value = {"result": self.old}
        with patch.object(p, "project_state", return_value=(self.project, self.deployments)), patch.object(p, "write_report"):
            p.delete_one(api, "verified", "a" * 32, self.old["id"], False)
        self.assertEqual(len(api.call.call_args_list), 1)
        self.assertNotIn("DELETE", str(api.call.call_args_list))

    def test_delete_disabled_even_with_valid_target(self):
        api = unittest.mock.Mock()
        api.call.return_value = {"result": self.old}
        with patch.dict(os.environ, {"CF_PAGES_DELETE_ENABLED": "false"}), patch.object(p, "project_state", return_value=(self.project, self.deployments)), patch.object(p, "write_report"), self.assertRaises(p.Stop):
            p.delete_one(api, "verified", "a" * 32, self.old["id"], True)
        self.assertNotIn("DELETE", str(api.call.call_args_list))

    def test_cannot_delete_current_even_when_enabled(self):
        api = unittest.mock.Mock()
        api.call.return_value = {"result": self.prod}
        with patch.dict(os.environ, {"CF_PAGES_DELETE_ENABLED": "true"}), patch.object(p, "project_state", return_value=(self.project, self.deployments)), patch.object(p, "write_report"), self.assertRaises(p.Stop):
            p.delete_one(api, "verified", "a" * 32, self.prod["id"], True)
        self.assertNotIn("DELETE", str(api.call.call_args_list))

    def test_batch_input_rejected_before_api(self):
        api = unittest.mock.Mock()
        with self.assertRaises(p.Stop):
            p.delete_one(api, "verified", "a" * 32, self.old["id"] + "," + self.latest["id"])
        api.call.assert_not_called()

    def test_approval_exact_snapshot_expiry_and_digest(self):
        now = dt.datetime.now(dt.timezone.utc)
        manifest = {"account_id": "a" * 32, "project_name": "verified", "approved_deployments": [{
            "deployment": p.summary(self.old), "approved_by": "tachikawagumi", "approval_record": "representative approval record",
            "approved_at": (now - dt.timedelta(minutes=1)).isoformat(), "expires_at": (now + dt.timedelta(days=1)).isoformat()}]}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "docs/cloudflare").mkdir(parents=True)
            data = json.dumps(manifest).encode()
            (root / "docs/cloudflare/deletion-approvals.json").write_bytes(data)
            digest = hashlib.sha256(data).hexdigest()
            with patch.object(p, "ROOT", root):
                p.approval(self.old, "verified", "a" * 32, digest, "tachikawagumi")
                for name, account, sha, actor in [("wrong", "a" * 32, digest, "tachikawagumi"), ("verified", "b" * 32, digest, "tachikawagumi"), ("verified", "a" * 32, "wrong", "tachikawagumi"), ("verified", "a" * 32, digest, "other")]:
                    with self.assertRaises(p.Stop):
                        p.approval(self.old, name, account, sha, actor)
                changed = copy.deepcopy(self.old)
                changed["aliases"] = ["https://new.example.pages.dev"]
                with self.assertRaises(p.Stop):
                    p.approval(changed, "verified", "a" * 32, digest, "tachikawagumi")

    def test_non_manual_or_non_main_rejected(self):
        for event, ref in [("push", "refs/heads/main"), ("pull_request", "refs/heads/main"), ("workflow_dispatch", "refs/heads/feature")]:
            with patch.dict(os.environ, {"GITHUB_EVENT_NAME": event, "GITHUB_REF": ref}), self.assertRaises(p.Stop):
                p.main()

    def test_single_delete_and_verification_no_force(self):
        api = unittest.mock.Mock()
        api.call.side_effect = [{"result": self.old}, {"result": self.old}, {"success": True}]
        with patch.dict(os.environ, {"CF_PAGES_DELETE_ENABLED": "true", "CONFIRMATION": "DELETE:" + self.old["id"]}), patch.object(
                p, "project_state", side_effect=[(self.project, self.deployments), (self.project, self.deployments),
                                                 (self.project, [self.latest, self.prod])]), patch.object(
                p, "approval") as approved, patch.object(p, "production_health", return_value={"ok": True}), patch.object(
                p, "inspect_urls", return_value=([{"result": "not-found", "http": 404}], [])), patch.object(p, "write_report") as report:
            p.delete_one(api, "verified", "a" * 32, self.old["id"], True)
            approved.assert_called_once()
            self.assertTrue(report.call_args.args[1]["executed"])
            self.assertTrue(report.call_args.args[1]["production_unchanged"])
        deletes = [c for c in api.call.call_args_list if c.kwargs.get("method") == "DELETE"]
        self.assertEqual(len(deletes), 1)
        self.assertTrue(deletes[0].args[0].endswith(self.old["id"]))
        self.assertNotIn("force", str(deletes))

    def test_race_production_changes_aborts_before_delete(self):
        api = unittest.mock.Mock()
        api.call.side_effect = [{"result": self.old}, {"result": self.old}]
        changed = copy.deepcopy(self.project)
        changed["canonical_deployment"] = self.latest
        with patch.dict(os.environ, {"CF_PAGES_DELETE_ENABLED": "true", "CONFIRMATION": "DELETE:" + self.old["id"]}), patch.object(
                p, "project_state", side_effect=[(self.project, self.deployments), (changed, self.deployments)]), patch.object(
                p, "approval"), patch.object(p, "production_health", return_value={"ok": True}), patch.object(p, "write_report"), self.assertRaises(p.Stop):
            p.delete_one(api, "verified", "a" * 32, self.old["id"], True)
        self.assertFalse(any(c.kwargs.get("method") == "DELETE" for c in api.call.call_args_list))

    def test_deletion_success_but_public_image_is_not_completion(self):
        api = unittest.mock.Mock()
        api.call.side_effect = [{"result": self.old}, {"result": self.old}, {"success": True}]
        with patch.dict(os.environ, {"CF_PAGES_DELETE_ENABLED": "true", "CONFIRMATION": "DELETE:" + self.old["id"]}), patch.object(
                p, "project_state", side_effect=[(self.project, self.deployments), (self.project, self.deployments),
                                                 (self.project, [self.latest, self.prod])]), patch.object(
                p, "approval"), patch.object(p, "production_health", return_value={"ok": True}), patch.object(
                p, "inspect_urls", return_value=([{"result": "image-public", "http": 200}], [])), patch.object(p, "write_report") as report, self.assertRaises(p.Stop):
            p.delete_one(api, "verified", "a" * 32, self.old["id"], True)
        self.assertTrue(report.call_args.args[1]["api_success"])

    def test_expired_approval_refused(self):
        now = dt.datetime.now(dt.timezone.utc)
        data = json.dumps({"account_id": "a" * 32, "project_name": "verified", "approved_deployments": [{
            "deployment": p.summary(self.old), "approved_by": "tachikawagumi", "approval_record": "approval",
            "approved_at": (now - dt.timedelta(days=2)).isoformat(), "expires_at": (now - dt.timedelta(days=1)).isoformat()}]}).encode()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "docs/cloudflare").mkdir(parents=True)
            (root / "docs/cloudflare/deletion-approvals.json").write_bytes(data)
            with patch.object(p, "ROOT", root), self.assertRaises(p.Stop):
                p.approval(self.old, "verified", "a" * 32, hashlib.sha256(data).hexdigest(), "tachikawagumi")

    def test_unknown_delete_response_records_attempt_not_success(self):
        api = unittest.mock.Mock()
        api.call.side_effect = [{"result": self.old}, {"result": self.old}, p.Stop("Cloudflare API HTTP 0")]
        with patch.dict(os.environ, {"CF_PAGES_DELETE_ENABLED": "true", "CONFIRMATION": "DELETE:" + self.old["id"]}), patch.object(
                p, "project_state", return_value=(self.project, self.deployments)), patch.object(
                p, "approval"), patch.object(p, "production_health", return_value={"ok": True}), patch.object(p, "write_report") as report, self.assertRaises(p.Stop):
            p.delete_one(api, "verified", "a" * 32, self.old["id"], True)
        self.assertTrue(report.call_args.args[1]["delete_attempted"])
        self.assertEqual(report.call_args.args[1]["api_outcome"], "unconfirmed")
        self.assertNotIn("api_success", report.call_args.args[1])
        self.assertEqual(sum(c.kwargs.get("method") == "DELETE" for c in api.call.call_args_list), 1)


if __name__ == "__main__":
    unittest.main()
