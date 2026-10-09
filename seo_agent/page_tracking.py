"""Bounded GET-only public observations. Failed sources never replace a baseline."""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup, Comment
from pydantic import Field

from .config import StrictModel, public_url, within_site
from .public_fetch import PublicFetcher, UA
from .storage import new_id, utc_now
from .tracking import actions, canonical, rows, timestamp


class Settings(StrictModel):
    enabled: bool = True
    interval_minutes: int = Field(default=360, ge=15, le=10080)
    max_pages: int = Field(default=6, ge=1, le=20)
    urls: list[str] = Field(default_factory=list, max_length=20)


class SiteRobots:
    """Keep URL-prefix isolation on every fetcher redirect as well as robots."""
    def __init__(self, root, parser):
        self.root, self.parser = root, parser

    def can_fetch(self, agent, url):
        return within_site(self.root, url) and self.parser.can_fetch(agent, url)


def settings(store, sid):
    store.site(sid)
    with store.db() as db:
        row = db.execute("SELECT payload FROM tracking_settings WHERE site_id=?", (sid,)).fetchone()
    return Settings.model_validate_json(row[0]).model_dump() if row else Settings().model_dump()


def save_settings(store, sid, value):
    store.require_private_write()
    s = Settings.model_validate(value).model_dump()
    if len(set(s["urls"])) != len(s["urls"]) or any(public_url(u) != u or not within_site(store.site(sid).url, u) for u in s["urls"]):
        raise ValueError("Track distinct exact selected-site URLs")
    with store.db() as db:
        db.execute("INSERT INTO tracking_settings VALUES (?,?) ON CONFLICT(site_id) DO UPDATE SET payload=excluded.payload", (sid, canonical(s)))


def tracked_urls(store, sid):
    s = settings(store, sid)
    urls = list(dict.fromkeys(s["urls"] + [a["payload"]["url"] for a in actions(store, sid)]))
    # Configured targets are explicit site-associated pages, not discovered pages.
    urls += [p.landing_page for p in store.site(sid).phrases if p.active and p.landing_page and p.landing_page not in urls]
    return urls[:s["max_pages"]]


def text_value(value):
    # Only presentation whitespace is normalized. Dates/prices/numbers remain.
    return re.sub(r"\s+", " ", value).strip()


def clean_content(soup):
    for n in soup.find_all(["script", "style", "template", "noscript"]):
        n.decompose()
    for n in list(soup.find_all(attrs={"hidden": True})) + list(soup.find_all(attrs={"aria-hidden": "true"})):
        if n.parent:
            n.decompose()
    for n in soup.find_all(string=lambda s: isinstance(s, Comment)):
        n.extract()


def extract(html, url, headers):
    soup = BeautifulSoup(html, "html.parser")
    title = text_value(soup.title.get_text(" ")) if soup.title else None
    if not soup.html or not soup.body or not title or soup.find(id=re.compile(r"^(cf-chl|challenge|captcha)", re.I)) or title.casefold() in {"just a moment...", "just a moment…", "attention required! | cloudflare", "verify you are human", "access denied"}:
        raise ValueError("Incomplete/challenged HTML is not page content")
    clean_content(soup)
    headings = [{"tag": n.name, "text": text_value(n.get_text(" "))} for n in soup.find_all(re.compile(r"^h[1-6]$"))]
    copy = [text_value(str(n)) for n in soup.body.find_all(string=True) if text_value(str(n))]
    if not copy or copy == ["Loading..."]:
        raise ValueError("Empty/script-only content cannot establish a page baseline")
    links = [{"text": text_value(n.get_text(" ")), "href": urljoin(url, n["href"])} for n in soup.find_all("a", href=True)]
    canonical_nodes = soup.find_all("link", rel=lambda v: v and "canonical" in v)
    canonical_value = urljoin(url, canonical_nodes[0].get("href", "")) if len(canonical_nodes) == 1 else None
    directives = [n.get("content", "") for n in soup.find_all("meta", attrs={"name": re.compile(r"^(robots|googlebot)$", re.I)})]
    return {"title": title, "headings": headings, "copy": copy, "links": links, "canonical": canonical_value,
        "index_directive": " | ".join(directives), "x_robots_tag": headers.get("X-Robots-Tag", ""),
        "limits": "Static HTML; script-rendered content, CSS visibility and CMS settings are not verified. Only whitespace/active markup normalized."}


def capture_target(store, sid, record):
    """Bind a preview target to its structural location, never to a page-wide value.

    Browser trees may differ from static HTML. Such differences deliberately leave
    publication review unavailable instead of guessing another matching element.
    """
    from .previews import load_preview, node_text
    a = record["payload"]
    targets = []
    for ref in a["evidence"]:
        if ref["revision"] is None or not ref["node_id"]:
            continue
        bundle = load_preview(store, sid, record["audit_id"], revision=ref["revision"])
        if not bundle:
            continue
        for page in bundle["pages"]:
            if page["url"] != a["url"] or page["tree"].get("tag") != "body":
                continue
            original = [v for v in page["actions"] if v.get("node_id") == ref["node_id"] and v["kind"] == a["action_kind"] and v["current"] == a["current"]]
            if len(original) != 1:
                continue
            def locate(node, path):
                if node.get("id") == ref["node_id"]:
                    return node, path
                children = [c for c in node.get("children", []) if "text" not in c or text_value(c["text"])]
                layout = ["#text" if "text" in c else c.get("tag") for c in children]
                counts = {}
                for child in children:
                    tag = child.get("tag")
                    if not tag:
                        continue
                    index = counts.get(tag, 0)
                    counts[tag] = index + 1
                    found = locate(child, path + [{"tag": tag, "index": index, "siblings": layout}])
                    if found:
                        return found
                return None
            located = locate(page["tree"], [])
            if not located:
                continue
            node, path = located
            source = original[0]
            child_index = source.get("text_child")
            before = node_text(node)
            if child_index is not None:
                before = node["children"][child_index]["text"]
                child_index = sum("text" not in c or bool(text_value(c["text"])) for c in node["children"][:child_index])
            if a["action_kind"] == "href":
                before = urljoin(a["url"], node["href"])
                after = urljoin(a["url"], a["proposed"])
            elif before.count(a["current"]) == 1:
                after = before.replace(a["current"], a["proposed"], 1)
            else:
                continue
            target = {"path": path, "text_child": child_index, "before": text_value(before), "after": text_value(after),
                      "current": a["current"], "proposed": a["proposed"],
                      "children": ["#text" if "text" in c else c.get("tag") for c in node.get("children", []) if "text" not in c or text_value(c["text"])]}
            if a["action_kind"] == "href":
                target["label"] = text_value(node_text(node))
            if target not in targets:
                targets.append(target)
    return targets[0] if len(targets) == 1 else None


def observed_value(values, a, *, proposed=False, target=None, html=None):
    candidate = a["proposed"] if proposed else a["current"]
    if candidate is None:
        return None
    kind = a["action_kind"]
    if kind in ("title", "canonical", "index_directive"):
        return values.get(kind)
    if kind in ("text", "href"):
        if not target or not html or target["current"] != a["current"] or target["proposed"] != a["proposed"]:
            return None
        soup = BeautifulSoup(html, "html.parser")
        clean_content(soup)
        node = soup.body
        if node is None:
            return None
        for step in target["path"]:
            children = [c for c in node.children if getattr(c, "name", None) or text_value(str(c))]
            if [c.name if getattr(c, "name", None) else "#text" for c in children] != step["siblings"]:
                return None
            matches = [c for c in children if getattr(c, "name", None) == step["tag"]]
            if not 0 <= step["index"] < len(matches):
                return None
            node = matches[step["index"]]
        children = [c for c in node.children if getattr(c, "name", None) or text_value(str(c))]
        if [c.name if getattr(c, "name", None) else "#text" for c in children] != target["children"]:
            return None
        if kind == "href":
            if node.name != "a" or text_value(node.get_text()) != target["label"]:
                return None
            actual = urljoin(a["url"], node.get("href", ""))
        elif target["text_child"] is not None:
            children = [c for c in node.children if getattr(c, "name", None) or text_value(str(c))]
            index = target["text_child"]
            if not 0 <= index < len(children) or getattr(children[index], "name", None):
                return None
            actual = str(children[index])
        else:
            actual = node.get_text()
        return candidate if text_value(actual) == target["after" if proposed else "before"] else None
    return None


def latest_snapshot(store, sid, url, *, successful=False):
    selected = [r for r in rows(store, "public_snapshots", sid) if r["url"] == url and (not successful or r["status"] == "complete")]
    return max(selected, key=lambda r: (r["checked"], r["id"])) if selected else None


def save_snapshot(store, sid, url, *, status, payload, checked=None, audit_id=None):
    store.require_private_write()
    if public_url(url) != url or not within_site(store.site(sid).url, url) or status not in {"complete", "unavailable"}:
        raise ValueError("Invalid snapshot site/source status")
    if audit_id:
        store.audit(sid, audit_id)
    checked = timestamp(checked or utc_now())
    if len(canonical(payload).encode()) > 3 * 1024 * 1024:
        raise ValueError("Snapshot exceeds source limit")
    if status == "complete":
        # Require the original response and reproducible extracted fields.
        if payload.get("values") != extract(payload["html"], url, payload.get("headers", {})) or payload.get("http_status") != 200 or payload.get("final_url") != url:
            raise ValueError("Snapshot must preserve exact successful source/values")
    before = latest_snapshot(store, sid, url, successful=True)
    if before and checked <= before["checked"]:
        raise ValueError("Observation timestamp must follow the saved baseline")
    snapid = new_id()
    with store.db() as db:
        db.execute("INSERT INTO public_snapshots VALUES (?,?,?,?,?,?,?)", (snapid, sid, url, checked, status, audit_id, canonical(payload)))
        if status == "complete":
            from .tracking import batch
            for approval in rows(store, "human_approvals", sid):
                b = batch(store, sid, approval["batch_id"])
                for frozen in b["payload"]["actions"]:
                    a = frozen["action"]
                    if a["url"] == url and observed_value(payload["values"], a, target=frozen.get("target"), html=payload["html"]) != a["current"]:
                        old = db.execute("SELECT 1 FROM approval_invalidations WHERE approval_id=? AND action_id=?", (approval["id"], frozen["action_id"])).fetchone()
                        if not old:
                            db.execute("INSERT INTO approval_invalidations VALUES (?,?,?,?,?,?,?)", (new_id(), sid, approval["id"], frozen["action_id"], frozen["revision"], checked, canonical({"reason": "Observed current value changed; approval cannot be reused even if the value later returns", "snapshot_id": snapid})))
        if status == "complete" and before:
            fields = ("title", "headings", "copy", "links", "canonical", "index_directive", "x_robots_tag")
            differences = {k: {"before": before["payload"]["values"].get(k), "after": payload["values"].get(k)} for k in fields if before["payload"]["values"].get(k) != payload["values"].get(k)}
            if differences:
                db.execute("INSERT INTO outside_changes VALUES (?,?,?,?,?)", (new_id(), sid, url, checked, canonical({"before_snapshot": before["id"], "after_snapshot": snapid,
                    "last_known_before_utc": before["checked"], "first_observed_after_utc": checked,
                    "author": "unknown", "publication_time": None, "approval": None, "action_id": None, "audit_id": audit_id,
                    "rationale": "unknown", "expected_effect": "unknown", "reviews": [], "diff": differences, "source": "Read-only public comparison; outside edit first observed, no automatic plan association"})))
    return snapid


def observe(store, sid, *, audit_id=None, demo=False, fetcher_factory=PublicFetcher, progress=None):
    config = store.site(sid)
    urls = tracked_urls(store, sid)
    if not urls:
        return {"status": "no tracked pages", "pages": 0}
    fetcher = None
    complete = 0
    started = time.monotonic()
    try:
        if not demo:
            fetcher = fetcher_factory(config.url, max_requests=min(121, 1 + 6 * len(urls)), timeout=8)
            robots = fetcher.get(urljoin(config.url, "/robots.txt"))
            if robots.status_code not in (200, 404) or (robots.status_code == 200 and ("<html" in robots.text.casefold() or "<script" in robots.text.casefold())):
                raise ValueError("Robots source unavailable/challenged")
            rp = RobotFileParser()
            rp.parse(robots.text.splitlines() if robots.status_code == 200 else [])
            site_robots = SiteRobots(config.url, rp)
        for number, url in enumerate(urls):
            if progress:
                progress(f"Public page {number + 1}/{len(urls)}")
            try:
                if time.monotonic() - started > 90:
                    raise ValueError("Tracking check time budget exceeded")
                if demo:
                    html = f"<html><head><title>Synthetic service</title></head><body><h1>Synthetic service</h1><p>Fixture copy.</p><a href='{config.url}'>Home</a></body></html>"
                    headers = {"content-type": "text/html"}
                    payload = {"html": html, "headers": headers, "http_status": 200, "final_url": url, "synthetic": True, "values": extract(html, url, headers)}
                else:
                    delay = rp.crawl_delay(UA) or 0
                    rate = rp.request_rate(UA)
                    if rate:
                        delay = max(delay, rate.seconds / rate.requests)
                    if delay > 5:
                        raise ValueError("Robots request pacing exceeds bounded check budget")
                    time.sleep(max(.2, delay))
                    response = fetcher.get(url, rp=site_robots)
                    if response.status_code != 200 or response.url != url or "html" not in response.headers.get("content-type", "").casefold():
                        raise ValueError("Unsuccessful/redirected source is unavailable")
                    headers = {k: response.headers.get(k, "") for k in ("content-type", "X-Robots-Tag")}
                    payload = {"html": response.text, "headers": headers, "http_status": 200, "final_url": url, "synthetic": False, "values": extract(response.text, url, headers)}
                save_snapshot(store, sid, url, status="complete", payload=payload, audit_id=audit_id)
                complete += 1
            except Exception:
                save_snapshot(store, sid, url, status="unavailable", payload={"reason": "Public content unavailable: robots, TLS, destination, challenge, redirect or incomplete HTML. Prior baseline preserved.", "synthetic": demo}, audit_id=audit_id)
    except Exception:
        for url in urls:
            save_snapshot(store, sid, url, status="unavailable", payload={"reason": "Robots/public source unavailable; no content comparison", "synthetic": demo}, audit_id=audit_id)
    finally:
        if fetcher:
            fetcher.close()
    return {"status": "complete" if complete == len(urls) else "partial" if complete else "unavailable", "pages": len(urls), "complete_pages": complete}


def refresh(store, sid, *, manual=False, demo=False, audit_id=None, progress=None, already_locked=False):
    """Persistent throttle plus the same audit/backup file lock; no rerun cache."""
    from .runner import GLOBAL_LOCK, run_lock
    from .trends import ingest_audits
    store.require_private_write()
    store.site(sid)
    if audit_id:
        store.audit(sid, audit_id)
    s = settings(store, sid)
    if not s["enabled"] and not manual:
        return {"status": "disabled"}
    def run():
        checks = rows(store, "tracking_checks", sid)
        last = checks[-1] if checks else None
        now = datetime.now(timezone.utc)
        # Manual refresh still has a short debounce to prevent replay/double click.
        delay = timedelta(seconds=15) if manual else timedelta(minutes=s["interval_minutes"])
        if last and now - datetime.fromisoformat(last["started"]) < delay:
            if audit_id:
                ingest_audits(store, sid)
            return {"status": "throttled", "last_checked": last["started"]}
        cid = new_id()
        payload = {"status": "running", "audit_id": audit_id, "trigger": "manual" if manual else "audit completion" if audit_id else "site open"}
        with store.db() as db:
            db.execute("INSERT INTO tracking_checks VALUES (?,?,?,NULL,?)", (cid, sid, utc_now(), canonical(payload)))
        try:
            ingest_audits(store, sid)
            result = observe(store, sid, audit_id=audit_id, demo=demo, progress=progress)
        except Exception:
            result = {"status": "failed", "reason": "Check failed; previous evidence preserved"}
        store.require_private_write()
        with store.db() as db:
            db.execute("UPDATE tracking_checks SET finished=?,payload=? WHERE id=? AND site_id=?", (utc_now(), canonical({**payload, **result}), cid, sid))
        return result
    if already_locked:
        return run()
    with run_lock(GLOBAL_LOCK):
        return run()
