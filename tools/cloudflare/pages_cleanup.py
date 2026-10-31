#!/usr/bin/env python3
"""Frozen inventory reconciliation and explicitly approved, bounded serial deletion.

No Access, domain, project configuration, GitHub mutation, force, or DELETE retry.
Shares API sanitization, pagination, production checks and blockers with pages_admin.
"""
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys

import pages_admin as p

PROJECT = "tachikawagumi-site"
REPOSITORY = "tachikawagumi/tachikawagumi-site"
SUBDOMAIN = PROJECT + ".pages.dev"
PRODUCTION = "b9f89a1f-cffa-427a-800d-98280178678a"
NEVER_DELETE = {PRODUCTION, "a0244d88-1233-478b-8c1d-cc031c227862"}
TRIAL_DELETED = "55ffe624-3398-4f08-9f8e-7441924fc90a"
MAX_BATCH = 25
PLAN_PATH = p.ROOT / "docs/cloudflare/cleanup-plan.json"
APPROVAL_PATH = p.ROOT / "docs/cloudflare/cleanup-approval.json"
SUMMARY_KEYS = {"id", "url", "aliases", "environment", "branch", "commit", "created_on", "stage", "status"}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def digest(value):
    return sha(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode())


def id_list(value):
    p.require(isinstance(value, list) and all(isinstance(x, str) and re.fullmatch(p.UUID, x) for x in value),
              "Invalid deployment ID list")
    p.require(len(set(value)) == len(value), "Duplicate deployment ID")
    return set(value)


def load_plan():
    raw = PLAN_PATH.read_bytes()
    plan = json.loads(raw)
    p.require(plan.get("schema_version") == 1 and plan.get("status") == "draft-not-approved",
              "Unexpected plan schema or status")
    p.require(plan.get("repository") == REPOSITORY and plan.get("project_name") == PROJECT
              and plan.get("subdomain") == SUBDOMAIN, "Wrong repository/project")
    p.require(plan.get("expected_production_id") == PRODUCTION
              and id_list(plan.get("never_delete_ids")) == NEVER_DELETE
              and plan.get("manually_deleted_ids") == [TRIAL_DELETED], "Protected IDs changed")
    candidates = id_list(plan.get("candidate_ids"))
    rows = plan.get("deployments")
    p.require(isinstance(rows, list) and len(rows) == 219 and len(candidates) == 177, "Frozen inventory count mismatch")
    ids = id_list([r.get("id") for r in rows])
    p.require(candidates <= ids and not candidates.intersection(NEVER_DELETE | {TRIAL_DELETED})
              and NEVER_DELETE <= ids and TRIAL_DELETED not in ids, "Unsafe candidate membership")
    for row in rows:
        p.require(set(row) == SUMMARY_KEYS | {"baseline_blockers"}, "Non-allowlisted plan fields")
        p.require(isinstance(row["baseline_blockers"], list), "Invalid blocker list")
        # Candidate metadata must contain only the hash URL; no arbitrary hosts/queries.
        p.require(row["url"] == "https://" + row["id"].split("-")[0] + "." + SUBDOMAIN,
                  "Unexpected deployment hash URL")
        if row["id"] in candidates:
            p.require(row["aliases"] == [] and row["baseline_blockers"] == []
                      and row["environment"] in {"production", "preview"}
                      and row["status"] in {"success", "failure", "canceled", "skipped"}
                      and bool(row["branch"]), "Protected/unknown candidate in frozen plan")
        else:
            p.require(bool(row["baseline_blockers"]), "Missing protected baseline")
    return plan, sha(raw)


def snapshots(plan, absent):
    return sorted(({k: row[k] for k in SUMMARY_KEYS} for row in plan["deployments"]
                   if row["id"] not in absent), key=lambda row: row["id"])


def state_hash(plan, absent):
    return digest({"production_id": PRODUCTION, "deployments": snapshots(plan, absent)})


def reconcile(project, deployments, plan, expected_absent=None):
    p.require(project.get("name") == PROJECT and project.get("subdomain") == SUBDOMAIN,
              "Project identity changed")
    p.require((project.get("canonical_deployment") or {}).get("id") == PRODUCTION,
              "Current production differs from protected approval baseline")
    ids = id_list([d.get("id") for d in deployments])
    baseline_ids = {r["id"] for r in plan["deployments"]}
    p.require(ids <= baseline_ids, "New deployment detected; stop and review, never auto-add")
    absent = baseline_ids - ids
    p.require(absent <= set(plan["candidate_ids"]), "Protected deployment missing")
    if expected_absent is not None:
        p.require(absent == set(expected_absent), "Deployment membership changed since preflight")
    p.require(sorted((p.summary(d) for d in deployments), key=lambda row: row["id"]) == snapshots(plan, absent),
              "Deployment snapshot/branch/alias/status changed")
    for target in deployments:
        if target["id"] in plan["candidate_ids"]:
            p.require(not p.protected(project, deployments, target), "Candidate is now protected; stop")
    return absent


class ScopedAPI(p.API):
    """No discovery of other projects and no configuration API surface."""
    def __init__(self, token, account, allowed_delete_ids=()):
        super().__init__(token, account)
        self.allowed_delete_ids = set(allowed_delete_ids)

    def call(self, path, method="GET"):
        route = "/pages/projects/" + PROJECT
        pattern = re.escape(route) + r"(?:/deployments(?:/(" + p.UUID + r"))?)?(?:\?page=[1-9][0-9]*&per_page=10)?"
        match = re.fullmatch(pattern, path)
        p.require(match is not None, "API route outside the single approved project")
        if method == "DELETE":
            p.require(path == route + "/deployments/" + (match.group(1) or "")
                      and match.group(1) in self.allowed_delete_ids
                      and match.group(1) not in NEVER_DELETE | {TRIAL_DELETED}, "DELETE outside approved IDs")
        else:
            p.require(method == "GET", "Only GET or approved deployment DELETE permitted")
        return super().call(path, method)


def trusted_main():
    p.require(os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
              and os.environ.get("GITHUB_REF") == "refs/heads/main"
              and os.environ.get("GITHUB_REPOSITORY") == REPOSITORY, "Only manual trusted main is permitted")
    commit = os.environ.get("GITHUB_SHA", "")
    p.require(bool(re.fullmatch(r"[0-9a-f]{40}", commit)), "Missing trusted main SHA")
    result = subprocess.run(["git", "ls-remote", "origin", "refs/heads/main"], capture_output=True,
                            text=True, timeout=20, check=False)
    p.require(result.returncode == 0 and result.stdout.split() == [commit, "refs/heads/main"],
              "Main changed or could not be verified")


def preflight(api, plan, plan_sha, account):
    project, deployments = p.project_state(api, PROJECT)
    absent = reconcile(project, deployments, plan)
    second, fresh = p.project_state(api, PROJECT)
    reconcile(second, fresh, plan, absent)
    report = {"schema_version": 1, "approved": False, "project_name": PROJECT,
              "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
              "run_id": os.environ.get("GITHUB_RUN_ID"), "plan_sha256": plan_sha,
              "account_sha256": sha(account.encode()), "state_sha256": state_hash(plan, absent),
              "production_id": PRODUCTION, "expected_absent_ids": sorted(absent),
              "absent_is_not_proof_of_deletion_or_url_closure": True,
              "candidate_deployments": [d for d in snapshots(plan, absent) if d["id"] in plan["candidate_ids"]],
              "protected_deployments": [d for d in plan["deployments"] if d["id"] not in plan["candidate_ids"]]}
    p.write_report("cleanup-preflight.json", report)
    print(f"Read-only reconciliation complete: {len(deployments)} present; "
          f"{len(report['candidate_deployments'])} fixed candidates. No DELETE or Access change.")


def load_approval(plan, plan_sha, account):
    raw = APPROVAL_PATH.read_bytes()
    approval_sha = sha(raw)
    p.require(approval_sha == os.environ.get("APPROVAL_SHA256"), "Approval SHA256 mismatch")
    approval = json.loads(raw)
    p.require(approval.get("schema_version") == 1 and approval.get("enabled") is True, "Approval remains disabled")
    p.require(approval.get("project_name") == PROJECT and approval.get("plan_sha256") == plan_sha
              and approval.get("account_sha256") == sha(account.encode()), "Approval account/project/plan mismatch")
    p.require(approval.get("approved_by") == os.environ.get("GITHUB_ACTOR") == "tachikawagumi"
              and os.environ.get("GITHUB_TRIGGERING_ACTOR") == "tachikawagumi", "Representative actor required")
    now = dt.datetime.now(dt.timezone.utc)
    approved, expires = p.timestamp(approval.get("approved_at")), p.timestamp(approval.get("expires_at"))
    p.require(approved <= now < expires and expires - approved <= dt.timedelta(days=7), "Approval expired/invalid")
    p.require(isinstance(approval.get("approval_record"), str) and bool(approval["approval_record"].strip())
              and bool(re.fullmatch(r"[0-9]+", str(approval.get("preflight_run_id", "")))), "Approval evidence/preflight missing")
    selected = id_list(approval.get("authorized_ids"))
    absent = id_list(approval.get("expected_absent_ids"))
    p.require(1 <= len(selected) <= MAX_BATCH and type(approval.get("max_deletions")) is int
              and len(selected) == approval["max_deletions"], "Exact bounded approval count required")
    p.require(selected <= set(plan["candidate_ids"]) and absent <= set(plan["candidate_ids"])
              and not selected.intersection(absent | NEVER_DELETE | {TRIAL_DELETED}), "Unapproved or protected ID")
    p.require(approval.get("state_sha256") == state_hash(plan, absent), "Preflight state hash mismatch")
    p.require(os.environ.get("CF_PAGES_DELETE_ENABLED") == "true", "Deletion environment disabled")
    p.require(os.environ.get("CONFIRMATION") == f"DELETE:{approval_sha}:{len(selected)}", "Exact hash/count confirmation required")
    return approval, approval_sha


def verify_closed(target):
    checks, skipped = p.inspect_urls(target, SUBDOMAIN)
    root = p.probe(p.origin(target["url"], SUBDOMAIN) + "/")
    checks.append(root)
    p.require(not skipped and len(checks) == len(p.PATHS) + 1, "Incomplete URL coverage")
    return checks, all(c["http"] in {404, 410} and c["result"] == "not-found" for c in checks)


def delete_batch(api, plan, approval, approval_sha, revalidate_approval):
    # No matrix/parallel DELETE. Selection/order is fixed by the approved file.
    selected = approval["authorized_ids"]
    absent = set(approval["expected_absent_ids"])
    report = {"approval_sha256": approval_sha, "production_id": PRODUCTION,
              "authorized_ids": selected, "completed_ids": [], "attempts": [], "complete": False}
    p.write_report("cleanup-deletion.json", report)
    for deployment_id in selected:
        trusted_main()
        fresh_approval, fresh_sha = revalidate_approval()
        p.require(fresh_sha == approval_sha and fresh_approval == approval, "Approval changed during execution")
        project, deployments = p.project_state(api, PROJECT)
        reconcile(project, deployments, plan, absent)
        report["production_before"] = p.production_health()
        p.write_report("cleanup-deletion.json", report)
        # Re-fetch after health checks, immediately before this one DELETE.
        trusted_main()
        revalidate_approval()
        project, deployments = p.project_state(api, PROJECT)
        reconcile(project, deployments, plan, absent)
        target = api.call(f"/pages/projects/{PROJECT}/deployments/{deployment_id}")["result"]
        baseline = next(d for d in snapshots(plan, absent) if d["id"] == deployment_id)
        p.require(p.summary(target) == baseline and not p.protected(project, deployments, target),
                  "Immediate target snapshot/blockers changed")
        attempt = {"id": deployment_id, "delete_attempted": True, "api_outcome": "unconfirmed"}
        report["attempts"].append(attempt)
        p.write_report("cleanup-deletion.json", report)
        try:
            api.call(f"/pages/projects/{PROJECT}/deployments/{deployment_id}", method="DELETE")
        except p.Stop:
            # A timeout may have committed the deletion: never automatically repeat it.
            try:
                report["production_after_unconfirmed"] = p.production_health()
            except p.Stop:
                report["production_after_unconfirmed"] = {"verified": False}
            p.write_report("cleanup-deletion.json", report)
            raise
        attempt.update(api_outcome="accepted", api_success=True)
        p.write_report("cleanup-deletion.json", report)
        try:
            project, deployments = p.project_state(api, PROJECT)
            reconcile(project, deployments, plan, absent | {deployment_id})
            checks, closed = verify_closed(target)
            attempt.update(checks=checks, public_urls_closed=closed)
            p.write_report("cleanup-deletion.json", report)
        finally:
            # An API/readback failure must not skip the independent production check.
            try:
                report["production_after"] = p.production_health()
            except p.Stop:
                report["production_after"] = {"verified": False}
                raise
            finally:
                p.write_report("cleanup-deletion.json", report)
        p.require(closed, "Delete accepted; URL closure incomplete. Stop before next ID")
        absent.add(deployment_id)
        report["completed_ids"].append(deployment_id)
        p.write_report("cleanup-deletion.json", report)
    report["complete"] = True
    p.write_report("cleanup-deletion.json", report)
    print(f"Verified {len(selected)} explicitly approved deletions; no other IDs changed by this job.")


def main():
    trusted_main()
    plan, plan_sha = load_plan()
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip().lower()
    p.require(os.environ.get("CLOUDFLARE_PAGES_PROJECT_NAME") == PROJECT, "Set the verified project variable")
    mode = os.environ.get("CLEANUP_MODE", "preflight")
    p.require(mode in {"preflight", "delete"}, "Invalid cleanup mode")
    if mode == "preflight":
        api = ScopedAPI(os.environ.get("CF_API_TOKEN", ""), account)
        preflight(api, plan, plan_sha, account)
    else:
        approval, approval_sha = load_approval(plan, plan_sha, account)
        api = ScopedAPI(os.environ.get("CF_API_TOKEN", ""), account, approval["authorized_ids"])
        delete_batch(api, plan, approval, approval_sha, lambda: load_approval(plan, plan_sha, account))


if __name__ == "__main__":
    try:
        main()
    except p.Stop as error:
        print("STOP: " + str(error), file=sys.stderr)
        sys.exit(1)
    except Exception:
        print("STOP: Unexpected response; no raw data or credentials logged.", file=sys.stderr)
        sys.exit(1)
