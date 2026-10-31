"""Read-only diagnostics. Never serialize API bodies, error messages or credentials."""
import datetime as dt
import os
import re
import urllib.parse

import pages_admin as p

FIELDS = ("id", "url", "aliases", "environment", "branch", "commit", "created_on", "stage", "status")
REASONS = {"current-production-unverified", "current-production", "branch-unknown", "latest-branch",
           "latest-successful-branch", "active-alias-no-force", "status-not-terminal", "environment-unknown"}
STAGES = {"queued", "initialize", "clone_repo", "build", "deploy"}
STATUSES = {"idle", "queued", "active", "success", "failure", "canceled", "skipped"}


def new_report(plan, plan_sha):
    run = os.environ.get("GITHUB_RUN_ID", "")
    return {"schema_version": 1, "approved": False, "read_only": True, "outcome": "incomplete",
            "phase": "first-api-read", "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "run_id": run if re.fullmatch(r"[0-9]+", run) else None,
            "project_name": "tachikawagumi-site", "plan_sha256": plan_sha,
            "baseline_count": len(plan["deployments"]), "fixed_candidate_count": len(plan["candidate_ids"]),
            "fixed_protected_count": len(plan["deployments"]) - len(plan["candidate_ids"]),
            "observations": [], "failure_category": None,
            "note": "Diagnostics never authorize deletion or update the fixed manifest."}


def secret_values():
    names = ("CF_API_TOKEN", "CLOUDFLARE_PAGES_READ_TOKEN", "CLOUDFLARE_PAGES_DELETE_TOKEN",
             "GITHUB_TOKEN", "GH_TOKEN", "CLOUDFLARE_ACCOUNT_ID")
    values = {os.environ.get(name, "").strip() for name in names}
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    return (values | {account.lower(), account.upper()}) - {""}


def snapshot(project, deployments, plan):
    issues = []
    secrets = secret_values()

    def text(value, pattern, label, maximum=256):
        if (not isinstance(value, str) or len(value) > maximum
                or any(s in value for s in secrets) or not re.fullmatch(pattern, value)):
            issues.append(label + ":invalid-or-withheld")
            return None
        return value

    def url(value, label):
        if not isinstance(value, str) or len(value) > 512 or any(s in value for s in secrets):
            issues.append(label + ":invalid-or-withheld")
            return None
        try:
            u = urllib.parse.urlsplit(value)
            host = u.hostname or ""
            good = (u.scheme == "https" and not u.username and not u.password and not u.port
                    and not u.query and not u.fragment and u.path in {"", "/"}
                    and bool(re.fullmatch(r"[a-z0-9.-]+", host))
                    and (host in {"tachikawagumi.co.jp", "tachikawagumi-site.pages.dev"}
                         or host.endswith(".tachikawagumi-site.pages.dev")))
        except ValueError:
            good = False
        if not good:
            issues.append(label + ":invalid-or-withheld")
            return None
        return value

    def safe_metadata(raw, label):
        if not isinstance(raw, dict):
            raw = {}
            issues.append(label + ":not-an-object")
        trigger = raw.get("deployment_trigger")
        trigger = trigger if isinstance(trigger, dict) else {}
        metadata = trigger.get("metadata")
        metadata = metadata if isinstance(metadata, dict) else {}
        stage = raw.get("latest_stage")
        stage = stage if isinstance(stage, dict) else {}
        aliases = raw.get("aliases")
        if aliases is None:
            aliases = []
        if not isinstance(aliases, list):
            issues.append(label + ".aliases:invalid-or-withheld")
            aliases = []
        created = text(raw.get("created_on"), r"[0-9TZ:+.\-]+", label + ".created_on", 40)
        if created is not None:
            try:
                p.timestamp(created)
            except p.Stop:
                issues.append(label + ".created_on:invalid-timestamp")
                created = None
        return {"id": text(raw.get("id"), p.UUID, label + ".id"),
                "url": url(raw.get("url"), label + ".url"),
                "aliases": [url(a, label + ".alias") for a in aliases],
                "environment": text(raw.get("environment"), r"production|preview", label + ".environment"),
                "branch": text(metadata.get("branch"), r"[A-Za-z0-9_./\-]+", label + ".branch"),
                "commit": text(metadata.get("commit_hash"), r"[0-9a-f]{40}", label + ".commit"),
                "created_on": created,
                "stage": text(stage.get("name"), "|".join(sorted(STAGES)), label + ".stage"),
                "status": text(stage.get("status"), "|".join(sorted(STATUSES)), label + ".status")}

    def baseline_raw(row):
        return {**row, "deployment_trigger": {"metadata": {"branch": row["branch"], "commit_hash": row["commit"]}},
                "latest_stage": {"name": row["stage"], "status": row["status"]}}

    canonical = project.get("canonical_deployment") if isinstance(project, dict) else None
    current = text(canonical.get("id") if isinstance(canonical, dict) else None, p.UUID, "current_production_id")
    if not isinstance(deployments, list):
        issues.append("deployments:not-a-list")
        deployments = []
    baseline = {r["id"]: r for r in plan["deployments"]}
    candidates = set(plan["candidate_ids"])
    rows, live, changed, protection_changes = [], {}, [], []
    for index, raw in enumerate(deployments):
        label = "deployment[" + str(index) + "]"
        before_issues = len(issues)
        safe = safe_metadata(raw, label)
        metadata_known = len(issues) == before_issues
        reasons, protection = [], "unknown"
        if metadata_known:
            try:
                reasons = p.protected(project, deployments, raw)
                if not isinstance(reasons, list) or any(r not in REASONS for r in reasons):
                    raise p.Stop("Unknown protection result")
                protection = "protected" if reasons else "unprotected"
            except (p.Stop, TypeError, ValueError, KeyError, AttributeError):
                issues.append(label + ".protection:unverified")
                reasons = []
        membership = ("fixed-candidate" if safe["id"] in candidates else
                      "fixed-protected" if safe["id"] in baseline else "new-unapproved")
        row = {"deployment": safe, "baseline_membership": membership,
               "fixed_deletion_candidate": safe["id"] in candidates,
               "runtime_protection": protection, "runtime_protection_reasons": reasons,
               "approved_for_deletion": False}
        rows.append(row)
        if safe["id"] is None:
            continue
        if safe["id"] in live:
            issues.append("deployments:duplicate-id")
        live[safe["id"]] = row
        if safe["id"] in baseline:
            old = baseline[safe["id"]]
            # Raw comparison preserves the existing comparator's exact attribute semantics.
            fields = [k for k in FIELDS if p.summary(raw).get(k) != old[k]] if metadata_known else list(FIELDS)
            if fields:
                changed.append({"id": safe["id"], "fields": fields,
                                "before": safe_metadata(baseline_raw(old), "baseline"), "after": safe})
            if protection != "unknown" and reasons != old["baseline_blockers"]:
                protection_changes.append({"id": safe["id"], "before": old["baseline_blockers"], "after": reasons})
    added = [live[i] for i in sorted(set(live) - set(baseline))]
    missing = [{"deployment": safe_metadata(baseline_raw(baseline[i]), "baseline"),
                "baseline_membership": "fixed-candidate" if i in candidates else "fixed-protected"}
               for i in sorted(set(baseline) - set(live))]
    return {"current_production_id": current, "expected_production_id": plan["expected_production_id"],
            "production_matches": current == plan["expected_production_id"],
            "observed_count": len(deployments), "new": added, "missing": missing, "changed": changed,
            "protection_changes": protection_changes, "unknown": sorted(set(issues)), "deployments": rows,
            "counts": {"new": len(added), "missing": len(missing), "changed": len(changed),
                       "protection_changes": len(protection_changes), "unknown": len(set(issues)),
                       "runtime_protected": sum(r["runtime_protection"] == "protected" for r in rows)}}


def reject_unknown_or_missing(observation):
    # Do not loosen reconcile(). Missing rows also need explicit human review.
    p.require(not observation["unknown"], "Preflight diagnostic metadata unknown; review sanitized artifacts")
    p.require(not observation["missing"], "Deployment missing from frozen inventory; review sanitized artifacts")
    p.require(not observation["protection_changes"], "Protection classification changed; review sanitized artifacts")


def markdown(report):
    def cell(value):
        # Metadata has already been validated; escape Markdown as defense in depth.
        value = "未確認" if value is None else str(value)
        return value.replace("\\", "\\\\").replace("|", "\\|").replace("`", "\\`").replace("\n", " ").replace("\r", " ")

    lines = ["# Cloudflare Pages preflight 診断", "", "**診断は削除承認ではありません。固定manifestは更新していません。**", "",
             "結果: " + cell(report["outcome"]), "", "段階: " + cell(report["phase"]), "",
             "固定一覧: " + str(report["baseline_count"]) + "件 / 候補: " + str(report["fixed_candidate_count"])
             + "件 / 保護: " + str(report["fixed_protected_count"]) + "件", ""]
    if not report["observations"]:
        lines += ["API情報の取得・検証が完了していません。最新件数・差分・本番IDは未確認です。", ""]
    for number, observation in enumerate(report["observations"], 1):
        lines += ["## API照合 " + str(number), "", "観測件数: " + str(observation["observed_count"]), "",
                  "本番ID: " + cell(observation["current_production_id"]), "",
                  "本番ID一致: " + str(observation["production_matches"]), "",
                  "差分件数: " + cell(observation["counts"]), ""]
        for key, title in [("new", "新規・未承認"), ("missing", "欠落（公開停止の証拠ではありません）")]:
            lines += ["### " + title, "", "| ID | 日時 | ブランチ | 環境 | 状態 | URL | alias | 実行時保護 | 保護理由 |",
                      "|---|---|---|---|---|---|---|---|---|"]
            for row in observation[key]:
                d = row["deployment"]
                values = [d["id"], d["created_on"], d["branch"], d["environment"], d["status"], d["url"],
                          ", ".join("未確認" if v is None else v for v in d["aliases"]) or "なし",
                          row.get("runtime_protection"), ", ".join(row.get("runtime_protection_reasons", [])) or "未確認/該当なし"]
                lines.append("| " + " | ".join(cell(v) for v in values) + " |")
            if not observation[key]:
                lines.append("| なし | | | | | | | | |")
            lines.append("")
        lines += ["### 属性変更", "", "| ID | 変更項目 | 変更前 | 変更後 |", "|---|---|---|---|"]
        for row in observation["changed"]:
            for field in row["fields"]:
                lines.append("| " + " | ".join(cell(v) for v in [row["id"], field, row["before"][field], row["after"][field]]) + " |")
        lines += ["", "### 保護判定の変化", ""]
        lines += ["- " + cell(row["id"]) + ": " + cell(row["before"]) + " → " + cell(row["after"])
                  for row in observation["protection_changes"]] or ["なし"]
        lines += ["", "### 不明・非公開化した項目", ""]
        lines += ["- " + cell(issue) for issue in observation["unknown"]] or ["なし"]
        lines.append("")
    return "\n".join(lines) + "\n"


def save(report):
    p.write_report("cleanup-diagnostics.json", report)
    (p.OUT / "cleanup-diagnostics.md").write_text(markdown(report), encoding="utf-8")
