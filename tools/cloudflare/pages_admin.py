#!/usr/bin/env python3
"""Manual Pages inventory / single approved deletion. Never persist API bodies or images."""
import concurrent.futures
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

PATHS = ["ashiba2.jpg", "ashiba3.jpg", "chika.jpg", "doko2.jpg", "hokyou.jpg", "torii.jpg"] + [
    "works/factory-roof-drainage-repair/photos/" + n for n in (
        "factory-roof-rainwater-drain.webp", "factory-leak-before.webp", "factory-leak-after.webp")]
ROOT = Path(__file__).resolve().parents[2]
OUT = Path(os.environ.get("REPORT_DIR", "pages-report"))
MAX_IMAGE = 16 * 1024 * 1024
UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"


class Stop(Exception):
    pass


def require(condition, message):
    if not condition:
        raise Stop(message)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request(url, token=None, method="GET", limit=MAX_IMAGE):
    headers = {"User-Agent": "Tachikawagumi-Pages-Admin/1.0"}
    if token:
        require(url.startswith("https://api.cloudflare.com/client/v4/accounts/"), "Invalid API origin")
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, headers=headers, method=method)
    try:
        with urllib.request.build_opener(NoRedirect).open(req, timeout=20) as response:
            body = response.read(limit + 1)
            return response.status, dict(response.headers), body
    except urllib.error.HTTPError as error:
        # Error pages may contain secrets or coordinates; do not return their body.
        return error.code, dict(error.headers), b""
    except (OSError, TimeoutError):
        return 0, {}, b""


class API:
    def __init__(self, token, account):
        require(bool(token), "Register the required Cloudflare token in GitHub Secrets")
        require(bool(re.fullmatch(r"[0-9a-f]{32}", account)), "Set CLOUDFLARE_ACCOUNT_ID from Cloudflare")
        self.token = token
        self.base = "https://api.cloudflare.com/client/v4/accounts/" + account

    def call(self, path, method="GET"):
        require(path.startswith("/pages/projects"), "Unexpected API path")
        status, _, body = request(self.base + path, self.token, method, 32 * 1024 * 1024)
        require(status == 200, f"Cloudflare API HTTP {status}; no raw response logged")
        try:
            data = json.loads(body)
        except (ValueError, UnicodeError):
            raise Stop("Invalid Cloudflare JSON response") from None
        require(data.get("success") is True, "Cloudflare API rejected request; no raw response logged")
        return data

    def all(self, path):
        results, seen = [], set()
        for page in range(1, 10001):
            data = self.call(path + f"?page={page}&per_page=100")
            batch = data.get("result")
            require(isinstance(batch, list), "Invalid paginated result")
            ids = [x.get("id") for x in batch]
            require(all(ids) and not seen.intersection(ids) and len(set(ids)) == len(ids),
                    "Pagination changed or repeated; rerun inventory")
            results.extend(batch)
            seen.update(ids)
            info = data.get("result_info") or {}
            # Do not assume the server honors per_page=100. Empty page is the fallback.
            if not batch or (info.get("total_pages") is not None and page >= int(info["total_pages"])):
                if info.get("total_count") is not None:
                    require(len(results) == int(info["total_count"]), "Incomplete pagination; rerun")
                return results
        raise Stop("Pagination safety limit reached; incomplete inventory")


def project_state(api, name):
    require(bool(re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", name)), "Set verified CLOUDFLARE_PAGES_PROJECT_NAME")
    path = "/pages/projects/" + name
    project = api.call(path)["result"]
    require(project.get("name") == name, "Project name mismatch")
    # Confirm the actual integration rather than deriving the project name from the repository.
    source = project.get("source") or {}
    config = source.get("config") or {}
    require(source.get("type") == "github" and config.get("owner") == "tachikawagumi"
            and config.get("repo_name") == "tachikawagumi-site", "Unexpected Pages GitHub integration")
    require("tachikawagumi.co.jp" in (project.get("domains") or []), "Official domain not attached to this project")
    subdomain = project.get("subdomain", "")
    require(bool(re.fullmatch(r"[a-z0-9-]+\.pages\.dev", subdomain)), "Unexpected Pages subdomain")
    deployments = api.all(path + "/deployments")
    return project, deployments


def timestamp(value):
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        require(parsed.tzinfo is not None, "Timestamp must have timezone")
        return parsed
    except (TypeError, ValueError, AttributeError):
        raise Stop("Missing/invalid deployment timestamp") from None


def metadata(d):
    return (d.get("deployment_trigger") or {}).get("metadata") or {}


def summary(d):
    m = metadata(d)
    # Explicit allowlist: env_vars, build_config, commit_message etc. are NEVER serialized.
    return {"id": d.get("id"), "url": d.get("url"), "aliases": d.get("aliases") or [],
            "environment": d.get("environment"), "branch": m.get("branch"),
            "commit": m.get("commit_hash"), "created_on": d.get("created_on"),
            "stage": (d.get("latest_stage") or {}).get("name"),
            "status": (d.get("latest_stage") or {}).get("status")}


def protected(project, deployments, target):
    reasons = []
    canonical = (project.get("canonical_deployment") or {}).get("id")
    if not canonical or not any(d.get("id") == canonical for d in deployments):
        reasons.append("current-production-unverified")
    if target.get("id") == canonical:
        reasons.append("current-production")
    branch = metadata(target).get("branch")
    if not branch:
        reasons.append("branch-unknown")
    else:
        group = [d for d in deployments if metadata(d).get("branch") == branch]
        # Protect latest attempt AND latest successful serving deployment, including tied dates.
        for label, members in [("latest-branch", group), ("latest-successful-branch", [
                d for d in group if (d.get("latest_stage") or {}).get("name") == "deploy"
                and (d.get("latest_stage") or {}).get("status") == "success"])]:
            if members and timestamp(target.get("created_on")) >= max(timestamp(d.get("created_on")) for d in members):
                reasons.append(label)
    if target.get("aliases"):
        reasons.append("active-alias-no-force")
    if (target.get("latest_stage") or {}).get("status") not in {"success", "failure", "canceled", "skipped"}:
        reasons.append("status-not-terminal")
    if target.get("environment") not in {"production", "preview"}:
        reasons.append("environment-unknown")
    return reasons


def origin(value, subdomain):
    try:
        p = urllib.parse.urlsplit(value)
        host = p.hostname or ""
        require(p.scheme == "https" and not p.username and not p.password and not p.port
                and not p.query and not p.fragment and p.path in {"", "/"}
                and (host == subdomain or host.endswith("." + subdomain)), "Non-Pages origin")
        require(bool(re.fullmatch(r"[a-z0-9.-]+", host)), "Invalid Pages hostname")
        return "https://" + host
    except (ValueError, TypeError):
        raise Stop("Invalid Pages origin") from None


def gps_ifd(tiff):
    """Read only EXIF IFD tag identifiers. Never decode GPS values."""
    if tiff.startswith(b"Exif\x00\x00"):
        tiff = tiff[6:]
    try:
        endian = {b"II": "<", b"MM": ">"}[tiff[:2]]
        require(struct.unpack_from(endian + "H", tiff, 2)[0] == 42, "Invalid TIFF")
        offset = struct.unpack_from(endian + "I", tiff, 4)[0]
        count = struct.unpack_from(endian + "H", tiff, offset)[0]
        require(offset + 2 + 12 * count + 4 <= len(tiff), "Truncated TIFF")
        return any(struct.unpack_from(endian + "H", tiff, offset + 2 + 12 * i)[0] == 0x8825 for i in range(count))
    except (KeyError, struct.error, Stop):
        return None


def image_metadata(body):
    if body.startswith(b"\xff\xd8"):
        offset, gps = 2, False
        while offset < len(body):
            if body[offset] != 255:
                return True, None
            while offset < len(body) and body[offset] == 255:
                offset += 1
            if offset >= len(body):
                return True, None
            marker = body[offset]
            offset += 1
            if marker in {0xDA, 0xD9}:
                return True, gps
            if marker in {0x01, *range(0xD0, 0xD8)}:
                continue
            if offset + 2 > len(body):
                return True, None
            size = int.from_bytes(body[offset:offset + 2], "big")
            if size < 2 or offset + size > len(body):
                return True, None
            segment = body[offset + 2:offset + size]
            if marker == 0xE1 and segment.startswith(b"Exif\x00\x00"):
                found = gps_ifd(segment)
                if found is True:
                    gps = True
                elif found is None and gps is False:
                    gps = None
            offset += size
        return True, None
    if body[:4] == b"RIFF" and body[8:12] == b"WEBP":
        offset, gps = 12, False
        end = int.from_bytes(body[4:8], "little") + 8
        if end > len(body):
            return True, None
        while offset + 8 <= end:
            kind, size = body[offset:offset + 4], int.from_bytes(body[offset + 4:offset + 8], "little")
            if offset + 8 + size > end:
                return True, None
            if kind == b"EXIF":
                found = gps_ifd(body[offset + 8:offset + 8 + size])
                gps = True if found is True or gps is True else found
            offset += 8 + size + size % 2
        return True, gps
    return False, None


def probe(url):
    status, headers, body = request(url)
    if len(body) > MAX_IMAGE:
        return {"url": url, "http": status, "result": "unknown-size-limit", "gps": None}
    image, gps = image_metadata(body) if status == 200 else (False, None)
    result = ("image-public" if image else "unknown-http-200") if status == 200 else (
        "not-found" if status in {404, 410} else "redirect-unverified" if 300 <= status < 400 else
        "access-denied-unverified" if status in {401, 403} else "unknown-network-or-http")
    # No Authorization sent to image hosts; no cookies; no redirect following; no body output.
    return {"url": url, "http": status, "result": result, "gps": gps}


def inspect_urls(d, subdomain):
    hosts, skipped = set(), []
    for value in [d.get("url"), *(d.get("aliases") or [])]:
        try:
            hosts.add(origin(value, subdomain))
        except Stop:
            # Keep only a hostname, never a query/userinfo supplied by an API response.
            skipped.append(urllib.parse.urlsplit(value or "").hostname or "invalid-origin")
    urls = sorted(h + "/" + p for h in hosts for p in PATHS)
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(probe, urls))
    return results, skipped


def production_health():
    base = "https://tachikawagumi.co.jp"
    status, _, body = request(base + "/sitemap.xml")
    require(status == 200, "Production sitemap unavailable; stop before any change")
    try:
        urls = [e.text for e in ET.fromstring(body).iter() if e.tag.endswith("}loc") or e.tag == "loc"]
    except ET.ParseError:
        raise Stop("Invalid production sitemap") from None
    require(len(urls) >= 15 and len(set(urls)) == len(urls), "Unexpected production sitemap")
    require(all(u and u.startswith(base + "/") for u in urls), "Unexpected sitemap origin")
    urls += [base + p for p in ("/robots.txt", "/style.css", "/styles.css", "/script.js",
                                "/assets/contact-ui.js", "/assets/contact-ui.css")]
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        statuses = list(pool.map(lambda u: {"url": u, "http": request(u)[0]}, urls))
    require(all(s["http"] == 200 for s in statuses), "Production URL failed; no deletion permitted")
    status, headers, _ = request("https://tachikawagumi-site.pages.dev/?pages-admin-check=1")
    location = next((v for k, v in headers.items() if k.lower() == "location"), "")
    require(status == 301 and location == base + "/?pages-admin-check=1", "Existing 301/query preservation check failed")
    return {"urls": statuses, "legacy_redirect": 301}


def write_report(name, data):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def inventory(api, name):
    project, deployments = project_state(api, name)
    report = {"project": name, "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
              "current_production": (project.get("canonical_deployment") or {}).get("id"), "deployments": []}
    for d in deployments:
        row = summary(d)
        reasons = protected(project, deployments, d)
        checks, skipped = inspect_urls(d, project["subdomain"])
        public = any(c["result"] == "image-public" for c in checks)
        all_missing = bool(checks) and all(c["result"] == "not-found" for c in checks) and not skipped
        row.update(current_production=row["id"] == report["current_production"],
                   latest_branch=any(r.startswith("latest-") for r in reasons),
                   deletion_blockers=reasons, deletion_candidate=not reasons,
                   image_state="public" if public else "not-found" if all_missing else "unverified",
                   checks=checks, additional_urls_unverified=skipped)
        report["deployments"].append(row)
    # Changing deployments during pagination/probing must not produce a stale approved inventory.
    again, fresh = project_state(api, name)
    require({d["id"] for d in fresh} == {d["id"] for d in deployments}
            and (again.get("canonical_deployment") or {}).get("id") == report["current_production"],
            "Deployments changed during inventory; rerun before approval")
    write_report("inventory.json", report)
    public_count = sum(d["image_state"] == "public" for d in report["deployments"])
    text = f"Inventory complete: {len(deployments)} deployments; {public_count} with publicly retrievable images.\n"
    text += "See sanitized inventory.json. 'candidate' is not approval; unverified is not blocked.\n"
    print(text)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        Path(os.environ["GITHUB_STEP_SUMMARY"]).write_text(text, encoding="utf-8")


def approval(target, name, account, digest, actor):
    manifest = ROOT / "docs/cloudflare/deletion-approvals.json"
    data_bytes = manifest.read_bytes()
    require(hashlib.sha256(data_bytes).hexdigest() == digest, "Approval file SHA256 mismatch")
    data = json.loads(data_bytes)
    require(data.get("account_id") == account and data.get("project_name") == name, "Approval project/account mismatch")
    entries = data.get("approved_deployments", [])
    matches = [e for e in entries if e.get("deployment", {}).get("id") == target["id"]]
    require(len(matches) == 1, "Exactly one matching representative-approved entry required")
    entry = matches[0]
    require(entry.get("approved_by") == actor == "tachikawagumi", "Representative approval/actor mismatch")
    now = dt.datetime.now(dt.timezone.utc)
    approved, expires = timestamp(entry.get("approved_at")), timestamp(entry.get("expires_at"))
    require(approved <= now < expires and expires - approved <= dt.timedelta(days=7), "Approval expired or invalid")
    require(bool(entry.get("approval_record")), "Representative approval evidence required")
    require(entry["deployment"] == summary(target), "Deployment changed since representative approval")


def delete_one(api, name, account, target_id, execute=False):
    require(bool(re.fullmatch(UUID, target_id)), "Specify exactly one valid Deployment ID")
    project, deployments = project_state(api, name)
    target = api.call(f"/pages/projects/{name}/deployments/{target_id}")["result"]
    require(target.get("id") == target_id and target_id in {d["id"] for d in deployments}, "Target mismatch")
    blockers = protected(project, deployments, target)
    report = {"target": summary(target), "blockers": blockers, "executed": False}
    write_report("deletion.json", report)
    if not execute:
        print("Dry run only; target snapshot and blockers written. No DELETE issued.")
        return
    require(not blockers, "Protected deployment: " + ", ".join(blockers))
    require(os.environ.get("CF_PAGES_DELETE_ENABLED") == "true", "Deletion disabled; representative must configure environment first")
    require(os.environ.get("CONFIRMATION") == "DELETE:" + target_id, "Exact single-ID confirmation required")
    approval(target, name, account, os.environ.get("APPROVAL_SHA256", ""), os.environ.get("GITHUB_ACTOR", ""))
    report["production_before"] = production_health()
    write_report("deletion.json", report)
    # Recheck immediately before deletion. Never pass force or retry a DELETE automatically.
    project2, fresh = project_state(api, name)
    target2 = api.call(f"/pages/projects/{name}/deployments/{target_id}")["result"]
    require(summary(target2) == summary(target) and not protected(project2, fresh, target2), "Safety state changed; deletion refused")
    require((project2.get("canonical_deployment") or {}).get("id") == (project.get("canonical_deployment") or {}).get("id"),
            "Production changed; deletion refused")
    api.call(f"/pages/projects/{name}/deployments/{target_id}", method="DELETE")
    # Record accepted operation before verification, even when verification later fails.
    report.update(executed=True, api_success=True)
    write_report("deletion.json", report)
    after, remaining = project_state(api, name)
    checks, skipped = inspect_urls(target, project["subdomain"])
    report.update(present_in_api=target_id in {d["id"] for d in remaining}, checks=checks,
                  additional_urls_unverified=skipped,
                  production_unchanged=(after.get("canonical_deployment") or {}).get("id") == (project.get("canonical_deployment") or {}).get("id"))
    write_report("deletion.json", report)
    report["production_after"] = production_health()
    write_report("deletion.json", report)
    require(not report["present_in_api"] and report["production_unchanged"], "Deletion/production verification incomplete")
    require(bool(checks) and not skipped and all(c["result"] == "not-found" for c in checks),
            "Deletion accepted but public URL closure not fully verified; inspect report")
    print("Single approved deployment deleted; tested image URLs return 404/410. Other historical paths are separate.")


def main():
    require(os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch" and os.environ.get("GITHUB_REF") == "refs/heads/main",
            "Only manual main workflow execution is permitted")
    require(os.environ.get("GITHUB_REPOSITORY") == "tachikawagumi/tachikawagumi-site", "Unexpected repository")
    mode = os.environ.get("MODE", "inventory")
    require(mode in {"discover", "inventory", "dry-run", "delete"}, "Unknown mode")
    if mode == "delete":
        require(os.environ.get("GITHUB_ACTOR") == "tachikawagumi" and os.environ.get("GITHUB_TRIGGERING_ACTOR") == "tachikawagumi",
                "Only representative may execute/rerun deletion")
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
    api = API(os.environ.get("CF_API_TOKEN", ""), account)
    name = os.environ.get("CLOUDFLARE_PAGES_PROJECT_NAME", "")
    if mode == "discover":
        projects = api.all("/pages/projects")
        safe = []
        for p in projects:
            c = (p.get("source") or {}).get("config") or {}
            safe.append({"name": p.get("name"), "subdomain": p.get("subdomain"),
                         "domains": p.get("domains") or [], "repository_owner": c.get("owner"), "repository_name": c.get("repo_name")})
        write_report("projects.json", safe)
        print("Project discovery complete. Verify repository + official domain before setting project variable.")
    elif mode == "inventory":
        inventory(api, name)
    else:
        delete_one(api, name, account, os.environ.get("DEPLOYMENT_ID", ""), execute=mode == "delete")


if __name__ == "__main__":
    try:
        main()
    except Stop as error:
        print("STOP: " + str(error), file=sys.stderr)
        sys.exit(1)
    except Exception:
        # Never print arbitrary API/transport exceptions, repr, traceback, token or response.
        print("STOP: Unexpected response; no sensitive details logged. Review configuration/tests.", file=sys.stderr)
        sys.exit(1)
