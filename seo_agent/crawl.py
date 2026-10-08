from __future__ import annotations

import json
import re
import time
from defusedxml import ElementTree as ET
from collections import deque, defaultdict
from urllib.parse import urljoin, urlsplit, urlunsplit, urldefrag
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup
import pandas as pd

from .public_fetch import PublicFetcher, UA
from .config import public_url, within_site

def normalize_url(url: str) -> str:
    url, _ = urldefrag(url)
    p = urlsplit(url)
    path = p.path or "/"
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), path, p.query, ""))

def same_host(a: str, b: str) -> bool:
    return urlsplit(a).netloc.lower() == urlsplit(b).netloc.lower()

def get_robot_parser(root_url: str, session: requests.Session) -> RobotFileParser:
    robots_url = urljoin(root_url, "/robots.txt")
    rp = RobotFileParser()
    rp.set_url(robots_url)
    try:
        resp = session.get(robots_url, timeout=15)
        # Other 2xx responses can be unfinished bot challenges, not robots rules.
        if resp.status_code == 200:
            rp.parse(resp.text.splitlines())
        elif resp.status_code == 404:
            rp.parse([])
        else:
            raise ValueError(f"Cannot safely crawl: robots.txt returned HTTP {resp.status_code}.")
    except requests.RequestException:
        raise ValueError("Cannot safely crawl: robots.txt could not be retrieved. Retry when the site is reachable.") from None
    return rp

def safe_get(url: str, root_url: str, session: requests.Session, rp: RobotFileParser):
    """Check host and robots rules before every request, including redirect targets."""
    if isinstance(session, PublicFetcher):
        return session.get(url, rp=rp)
    for _ in range(10):
        if not same_host(root_url, url) or not rp.can_fetch(UA, url):
            raise ValueError("Request or redirect blocked by host boundary or robots.txt")
        response = session.get(url, timeout=20, allow_redirects=False)
        if response.status_code in (301, 302, 303, 307, 308) and response.headers.get("Location"):
            url = normalize_url(urljoin(url, response.headers["Location"]))
            continue
        return response
    raise ValueError("Too many redirects")

def discover_sitemaps(root_url: str, rp: RobotFileParser) -> list[str]:
    candidates = list(rp.site_maps() or [])
    for guess in ("/sitemap_index.xml", "/wp-sitemap.xml", "/sitemap.xml"):
        candidates.append(urljoin(root_url, guess))
    seen, out = set(), []
    for u in candidates:
        u = normalize_url(u)
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out

def sitemap_urls(sitemap_url: str, session: requests.Session, max_sitemaps: int = 50, *, root_url: str, rp: RobotFileParser) -> set[str]:
    found_urls = set()
    q = deque([sitemap_url])
    seen = set()
    while q and len(seen) < max_sitemaps:
        sm = q.popleft()
        if sm in seen:
            continue
        seen.add(sm)
        try:
            r = safe_get(sm, root_url, session, rp)
            if not r.ok or "xml" not in (r.headers.get("content-type", "") + sm):
                continue
            root = ET.fromstring(r.content, forbid_dtd=True, forbid_entities=True, forbid_external=True)
        except Exception:
            continue
        kind = root.tag.rsplit("}", 1)[-1]
        # Only direct sitemap/url locations are crawl seeds, never image/video locs.
        for entry in root:
            for elem in entry:
                if elem.tag == root.tag.replace(kind, "loc") and elem.text:
                    loc = normalize_url(elem.text.strip())
                    if kind == "sitemapindex":
                        q.append(loc)
                    elif kind == "urlset":
                        found_urls.add(loc)
                        if len(found_urls) >= 1000:
                            return found_urls
    return found_urls

def _jsonld_types(soup: BeautifulSoup) -> list[str]:
    types = set()
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = tag.string or tag.get_text()
        if not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        stack = [data]
        while stack:
            obj = stack.pop()
            if isinstance(obj, dict):
                t = obj.get("@type")
                if isinstance(t, str):
                    types.add(t)
                elif isinstance(t, list):
                    types.update(str(x) for x in t)
                stack.extend(obj.values())
            elif isinstance(obj, list):
                stack.extend(obj)
    return sorted(types)

def analyze_html(url: str, final_url: str, status: int, html: str, config=None) -> tuple[dict, set[str]]:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True)[:1000] if soup.title else ""
    desc = ""
    tag = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    if tag:
        desc = tag.get("content", "").strip()[:2000]
    robots = ""
    tag = soup.find("meta", attrs={"name": re.compile("^robots$", re.I)})
    if tag:
        robots = tag.get("content", "").strip()
    canonical = ""
    tag = soup.find("link", attrs={"rel": lambda x: x and "canonical" in x})
    if tag:
        canonical = urljoin(final_url, tag.get("href", "")).strip()

    headings = {}
    for level in range(1, 7):
        vals = [h.get_text(" ", strip=True) for h in soup.find_all(f"h{level}")]
        headings[f"h{level}"] = " | ".join(v for v in vals if v)[:5000]

    for bad in soup(["script", "style", "noscript", "svg"]):
        bad.decompose()
    text = " ".join(soup.stripped_strings)
    words = re.findall(r"\b[\w'-]+\b", text)

    internal_links = set()
    all_links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        absolute = normalize_url(urljoin(final_url, href))
        all_links.add(absolute)
        if same_host(final_url, absolute):
            internal_links.add(absolute)

    images = soup.find_all("img")
    missing_alt = sum(1 for im in images if not im.has_attr("alt") or not im.get("alt", "").strip())

    row = {
        "url": url,
        "final_url": final_url,
        "status": status,
        "title": title,
        "meta_description": desc,
        "robots_meta": robots,
        "canonical": canonical,
        **headings,
        "word_count": len(words),
        "image_count": len(images),
        "images_missing_alt": missing_alt,
        "schema_types": " | ".join(_jsonld_types(BeautifulSoup(html, "html.parser"))),
        "internal_links_out": len(internal_links),
        "text_mentions_paoli": bool(re.search(r"\bPaoli\b", text, re.I)),
        "text_mentions_adhd": bool(re.search(r"\bADHD\b", text, re.I)),
        "text_mentions_assessment": bool(re.search(r"\b(assessment|evaluation|testing)\b", text, re.I)),
    }
    return row, internal_links

def crawl(root_url: str, out_csv, max_pages: int = 200, delay: float = 0.25, *, config=None, progress=None) -> pd.DataFrame:
    root_url = public_url(normalize_url(root_url))
    if urlsplit(root_url).scheme not in ("http", "https") or not urlsplit(root_url).netloc:
        raise ValueError("Website URL must be an absolute http(s) URL.")
    if not 1 <= max_pages <= 200:
        raise ValueError("Crawl must be bounded to 1–200 pages")
    session = PublicFetcher(root_url, max_requests=min(max_pages * 3 + 60, 660))
    try:
        rp = get_robot_parser(root_url, session)
    except Exception:
        session.close()
        raise

    seeds = {root_url}
    for sm in discover_sitemaps(root_url, rp):
        seeds |= {u for u in sitemap_urls(sm, session, max_sitemaps=10, root_url=root_url, rp=rp) if same_host(root_url, u) and within_site(root_url, u)}

    q = deque([root_url] + sorted(seeds - {root_url}))
    seen = set()
    rows = []
    inbound = defaultdict(int)
    delay = max(delay, rp.crawl_delay(UA) or rp.crawl_delay("*") or 0)
    rate = rp.request_rate(UA) or rp.request_rate("*")
    if rate:
        delay = max(delay, rate.seconds / rate.requests)

    while q and len(seen) < max_pages:
        url = q.popleft()
        if url in seen or not same_host(root_url, url) or not within_site(root_url, url):
            continue
        if not rp.can_fetch(UA, url):
            seen.add(url)
            rows.append({"url": url, "status": "blocked_by_robots"})
            continue
        seen.add(url)
        try:
            resp = safe_get(url, root_url, session, rp)
        except (requests.RequestException, ValueError) as exc:
            rows.append({"url": url, "status": "request_error", "error": str(exc)})
            continue

        ctype = resp.headers.get("content-type", "")
        if "text/html" not in ctype or urlsplit(resp.url).path.lower().endswith((".kml", ".xml")):
            rows.append({"url": url, "final_url": resp.url, "status": resp.status_code, "content_type": ctype})
            continue

        row, links = analyze_html(url, resp.url, resp.status_code, resp.text, config=config)
        if config is not None:
            for key in ("text_mentions_paoli", "text_mentions_adhd", "text_mentions_assessment"):
                row.pop(key, None)
            row["configured_location_present"] = bool(config.location and config.location.casefold() in BeautifulSoup(resp.text, "html.parser").get_text(" ", strip=True).casefold())
        row["content_type"] = ctype
        row["x_robots_tag"] = resp.headers.get("X-Robots-Tag", "")
        row["internal_link_urls"] = json.dumps(sorted(links))
        rows.append(row)
        for link in links:
            inbound[link] += 1
            if link not in seen and len(q) < max_pages * 10:
                q.append(link)
        if progress:
            progress(f"Crawled {len(seen)} / {max_pages} bounded pages")
        time.sleep(delay)

    df = pd.DataFrame(rows)
    if not df.empty:
        df["internal_links_in"] = df["url"].map(lambda u: inbound.get(u, 0))
        if "title" in df.columns:
            df["duplicate_title"] = df["title"].fillna("").duplicated(keep=False) & df["title"].fillna("").ne("")
        if "meta_description" in df.columns:
            df["duplicate_description"] = (
                df["meta_description"].fillna("").duplicated(keep=False)
                & df["meta_description"].fillna("").ne("")
            )
    df.to_csv(out_csv, index=False)
    session.close()
    return df
