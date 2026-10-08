"""Site-scoped appearance. Public CSS is data, never executable app styling."""
from __future__ import annotations

import base64
import json
import re
import time
from collections import Counter
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from .config import public_url
from .crawl import get_robot_parser
from .public_fetch import PublicFetcher
from .storage import checked_id, child_path, historical_date, utc_now

MAX_APPEARANCE = 2 * 1024 * 1024
DEFAULT = {"background": "#ffffff", "surface": "#f5f5f4", "text": "#292524", "accent": "#52635c",
           "heading_font": "Georgia", "body_font": "Arial", "fonts": []}


def font_name(value):
    value = value.split(",")[0].strip().strip("\"'")
    if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9 -]{0,69}", value):
        raise ValueError("Unsupported font family")
    return value


def color(value):
    value = value.strip().lower()
    if re.fullmatch(r"#[0-9a-f]{3}", value):
        return "#" + "".join(c * 2 for c in value[1:])
    if re.fullmatch(r"#[0-9a-f]{6}", value):
        return value
    match = re.fullmatch(r"rgb\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)", value)
    if match and all(int(v) < 256 for v in match.groups()):
        return "#" + "".join(f"{int(v):02x}" for v in match.groups())
    raise ValueError("Unsupported appearance color")


def luminance(value):
    rgb = [int(value[i:i+2], 16) / 255 for i in (1, 3, 5)]
    rgb = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in rgb]
    return sum(v * weight for v, weight in zip(rgb, (.2126, .7152, .0722)))


def contrast(a, b):
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + .05) / (low + .05)


def font_asset(family, content, *, italic=False, weight="100 900"):
    family = font_name(family)
    if not 4 <= len(content) <= 350000 or content[:4] not in (b"wOF2", b"wOFF"):
        raise ValueError("Only bounded WOFF/WOFF2 font files are supported")
    if not re.fullmatch(r"[1-9]00(?: [1-9]00)?", weight):
        raise ValueError("Unsupported font weight")
    return {"family": family, "style": "italic" if italic else "normal", "weight": weight,
            "data": "data:font/" + ("woff2" if content[:4] == b"wOF2" else "woff") + ";base64," + base64.b64encode(content).decode()}


def validate_appearance(value, sid, url):
    if not isinstance(value, dict) or value.get("site_id") != checked_id(sid) or value.get("url") != public_url(url):
        raise ValueError("Appearance belongs to a different site")
    historical_date(value["captured_utc"])
    if value.get("status") not in ("captured", "partial", "unavailable", "synthetic") or len(value.get("note", "")) > 1000:
        raise ValueError("Invalid appearance status")
    clean = {k: value[k] for k in ("site_id", "url", "captured_utc", "status", "note")}
    for key in ("background", "surface", "text", "accent"):
        clean[key] = color(value[key])
    # Imported colors must leave ordinary app text readable.
    if contrast(clean["background"], clean["text"]) < 4.5 or contrast(clean["surface"], clean["text"]) < 4.5:
        clean.update(background=DEFAULT["background"], surface=DEFAULT["surface"], text=DEFAULT["text"])
    for key in ("heading_font", "body_font"):
        clean[key] = font_name(value[key])
    fonts = value.get("fonts", [])
    if not isinstance(fonts, list) or len(fonts) > 4:
        raise ValueError("Too many appearance fonts")
    clean["fonts"] = []
    for asset in fonts:
        match = re.fullmatch(r"data:font/(woff2?);base64,([A-Za-z0-9+/=]+)", asset["data"])
        if not match or len(asset["data"]) > 470000:
            raise ValueError("Invalid font data")
        raw = base64.b64decode(match[2], validate=True)
        if (match[1] == "woff2") != (raw[:4] == b"wOF2") or asset.get("style") not in ("normal", "italic"):
            raise ValueError("Font format/style mismatch")
        clean["fonts"].append(font_asset(asset["family"], raw, italic=asset["style"] == "italic", weight=asset["weight"]))
    if len(json.dumps(clean)) > MAX_APPEARANCE:
        raise ValueError("Appearance exceeds size limit")
    return clean


def appearance_path(store, sid):
    store.site(sid)
    return child_path(store.root, "sites", checked_id(sid), "appearance.json")


def save_appearance(store, sid, value):
    store.require_private_write()
    value = validate_appearance(value, sid, store.site(sid).url)
    path = appearance_path(store, sid)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value), encoding="utf-8")
    temporary.replace(path)
    return value


def load_appearance(store, sid):
    path = appearance_path(store, sid)
    if not path.is_file():
        return None
    if path.stat().st_size > MAX_APPEARANCE:
        raise ValueError("Appearance exceeds size limit")
    return validate_appearance(json.loads(path.read_text(encoding="utf-8")), sid, store.site(sid).url)


def css_appearance(css):
    """Best-effort extraction of common theme tokens; do not execute selectors/CSS."""
    css = re.sub(r"/\*.*?\*/", "", css[:1500000], flags=re.S)
    result = dict(DEFAULT)
    candidates = Counter()
    for declaration in re.findall(r"(?:color|--[\w-]*(?:color|primary|accent|secondary)[\w-]*)\s*:\s*([^;{}]+)", css, re.I):
        try:
            c = color(declaration)
            channels = [int(c[i:i+2], 16) for i in (1, 3, 5)]
            if max(channels) - min(channels) > 25 and .07 < luminance(c) < .8:
                candidates[c] += 1
        except ValueError:
            pass
    if candidates:
        result["accent"] = candidates.most_common(1)[0][0]
    for selector, declarations in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        declarations = {k.lower(): v.strip().removesuffix("!important").strip() for k, v in re.findall(r"([\w-]+)\s*:\s*([^;]+)", declarations)}
        if re.search(r"(?:^|[,\s])(?:body|html)(?:$|[,\s])", selector.strip()):
            for source, target in (("background-color", "background"), ("color", "text")):
                if source in declarations:
                    try:
                        result[target] = color(declarations[source])
                    except ValueError:
                        pass
        for role, pattern in (("heading_font", r"(?:^|[,\s])h[1-3](?:$|[,\s])"), ("body_font", r"(?:^|[,\s])(?:body|p)(?:$|[,\s])")):
            if re.search(pattern, selector.strip()) and "font-family" in declarations:
                try:
                    result[role] = font_name(declarations["font-family"])
                except ValueError:
                    pass
        for source, target in (("--e-global-typography-primary-font-family", "heading_font"), ("--e-global-typography-text-font-family", "body_font")):
            if source in declarations:
                try:
                    result[target] = font_name(declarations[source])
                except ValueError:
                    pass
    return result


def capture_appearance(store, sid, *, demo=False):
    """At site creation/refresh only: robots + homepage + bounded same-host CSS/fonts."""
    store.require_private_write()
    config = store.site(sid)
    value = {**DEFAULT, "site_id": sid, "url": config.url, "captured_utc": utc_now(),
             "status": "unavailable", "note": "Appearance could not be read. A readable default is in use."}
    if demo:
        value.update(status="synthetic", note="Demonstration appearance; no public requests were made.")
        return save_appearance(store, sid, value)
    fetcher = PublicFetcher(config.url, max_requests=10, max_bytes=600000, timeout=3)
    deadline = time.monotonic() + 18
    def get(url, rp):
        if time.monotonic() > deadline:
            raise ValueError("Appearance time budget reached")
        response = fetcher.get(url, rp=rp)
        if response.status_code != 200:
            raise ValueError(f"Public appearance request returned HTTP {response.status_code}")
        return response
    try:
        rp = get_robot_parser(config.url, fetcher)
        response = get(config.url, rp)
        if "html" not in response.headers.get("Content-Type", response.headers.get("content-type", "")):
            raise ValueError("Homepage did not return HTML")
        soup = BeautifulSoup(response.content, "html.parser")
        css_parts = [tag.get_text() for tag in soup.find_all("style")]
        links = []
        for link in soup.select('link[rel="stylesheet"][href]'):
            url = urljoin(response.url, link["href"])
            try:
                url = public_url(url)
                if urlsplit(url).netloc == urlsplit(config.url).netloc and url not in links:
                    links.append(url)
            except ValueError:
                continue
        # Prefer theme/site styles over plugin reset sheets; external imports stay inert.
        links.sort(key=lambda u: (0 if "/uploads/" in u and "/css/post-" in u else 1 if "font" in u else 2 if "/themes/" in u else 3))
        sources = []
        incomplete = len(links) > 5
        for url in links[:5]:
            try:
                response = get(url, rp)
                if "css" in response.headers.get("Content-Type", response.headers.get("content-type", "")):
                    css_parts.append(response.text)
                    sources.append((response.url, response.text))
            except ValueError:
                incomplete = True
        value.update(css_appearance("\n".join(css_parts)))
        fonts = []
        wanted = {value["heading_font"], value["body_font"]}
        for source_url, css in sources:
            for face in re.findall(r"@font-face\s*\{([^}]+)\}", css, re.I):
                family = re.search(r"font-family\s*:\s*([^;]+)", face, re.I)
                src = re.search(r"url\(['\"]?([^)'\"]+)['\"]?\)", face, re.I)
                if not family or not src or len(fonts) >= 3:
                    continue
                try:
                    family = font_name(family[1])
                    url = public_url(urljoin(source_url, src[1]))
                    if family not in wanted or any(f["family"] == family for f in fonts) or urlsplit(url).netloc != urlsplit(config.url).netloc:
                        continue
                    weight = re.search(r"font-weight\s*:\s*([\d ]+)", face, re.I)
                    fonts.append(font_asset(family, get(url, rp).content, italic=bool(re.search(r"font-style\s*:\s*italic", face)), weight=weight[1].strip() if weight else "400"))
                except ValueError:
                    incomplete = True
        value["fonts"] = fonts
        incomplete |= bool(wanted - {f["family"] for f in fonts} - {"Arial", "Georgia"})
        value.update(status="partial" if incomplete else "captured", note="Colors and typography read from public styles. " + ("Some styles/fonts were unavailable; local fallbacks are used." if incomplete else "Fonts are saved locally."))
    except ValueError as exc:
        value["note"] = str(exc)[:700] + " Readable default appearance is in use. Refresh when public access is available."
    finally:
        fetcher.close()
    return save_appearance(store, sid, value)


def font_css(value):
    return "".join("@font-face{font-family:'" + font_name(f["family"]) + "';font-style:" + f["style"] + ";font-weight:" + f["weight"] + ";font-display:swap;src:url('" + f["data"] + "')}" for f in value.get("fonts", []))


def app_css(value=None):
    a = value or DEFAULT
    ink = a["text"] if contrast(a["text"], a["surface"]) >= 4.5 else "#292524"
    accent_ink = "#ffffff" if contrast(a["accent"], "#ffffff") >= 4.5 else "#111111"
    return "<style>" + font_css(a) + f"""
    .stApp {{background:{a['background']};color:{ink};font-family:'{a['body_font']}',Arial,sans-serif}}
    [data-testid="stSidebar"] {{background:{a['surface']}}}
    .stApp h1,.stApp h2,.stApp h3,.review-report h1,.review-report h2,.review-report h3 {{font-family:'{a['heading_font']}',Georgia,serif!important;color:{ink}}}
    .stApp p,.stApp label,.stApp li {{font-family:'{a['body_font']}',Arial,sans-serif!important}}
    [data-testid="stBaseButton-primary"] {{background:{a['accent']};color:{accent_ink};border-color:{a['accent']}}}
    .review-report {{font-family:'{a['body_font']}',Arial,sans-serif;line-height:1.75;max-width:1000px;color:{ink}}}
    .review-report h1 {{font-size:2.2rem;line-height:1.25;margin:1rem 0}}
    .review-report h2 {{font-size:1.6rem;margin:2rem 0 .7rem;border-bottom:2px solid {a['accent']};padding-bottom:.4rem}}
    .review-report h3 {{font-size:1.3rem;margin:1.5rem 0 .5rem}}
    .review-report p {{margin:.6rem 0 1rem}} .review-report li {{margin:.4rem 0}}
    .review-report table {{border-collapse:collapse;width:100%;margin:1rem 0;font-size:.94rem}}
    .review-report th {{background:{a['surface']};text-align:left}}
    .review-report td,.review-report th {{border:1px solid #d6d3d1;padding:.6rem .75rem;vertical-align:top}}
    .review-report code {{background:{a['surface']};padding:.1rem .3rem;overflow-wrap:anywhere}}
    .review-report blockquote {{border-left:3px solid {a['accent']};padding:.6rem 1rem;background:{a['surface']};margin:1rem 0}}
    </style>"""
