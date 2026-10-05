from __future__ import annotations

import re
from pathlib import Path
import pandas as pd

TARGET_PATTERNS = [
    (r"\badhd\b.*\b(assessment|testing|evaluation)\b|\b(assessment|testing|evaluation)\b.*\badhd\b", "adhd_assessment"),
    (r"\btherapy\b|\btherapist\b|\bcounsel", "therapy"),
    (r"\bpsychological\b.*\b(test|assessment|evaluation)", "psychological_testing"),
]
LOCAL_PATTERNS = [r"\bpaoli\b", r"\bnear me\b"]

def classify_query(q: str) -> str:
    q = (q or "").lower()
    labels = []
    for pat, label in TARGET_PATTERNS:
        if re.search(pat, q):
            labels.append(label)
    if any(re.search(p, q) for p in LOCAL_PATTERNS):
        labels.append("local")
    return ",".join(labels) or "other"

def build_opportunities(data_dir: Path) -> pd.DataFrame:
    path = data_dir / "gsc_query_page.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    if df.empty:
        return df
    df["intent"] = df["query"].fillna("").map(classify_query)

    def opp(row):
        imp, pos, ctr = row.get("impressions", 0), row.get("position", 999), row.get("ctr", 0)
        if imp >= 25 and 4 <= pos <= 20:
            return "striking_distance"
        if imp >= 25 and 20 < pos <= 50:
            return "relevance_or_authority_gap"
        if imp >= 50 and pos <= 10 and ctr < 0.03:
            return "low_ctr"
        if row["intent"] != "other" and imp > 0:
            return "target_query"
        return ""

    df["opportunity_type"] = df.apply(opp, axis=1)
    df["priority_score"] = (
        df["impressions"].fillna(0).clip(upper=500) / 100
        + (51 - df["position"].fillna(51).clip(upper=51)) / 10
        + df["intent"].ne("other").astype(int) * 3
    ).round(2)
    return df.sort_values(["priority_score", "impressions"], ascending=False)

def write_markdown_summary(data_dir: Path, reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    opp = build_opportunities(data_dir)
    crawl_path = data_dir / "crawl.csv"
    crawl = pd.read_csv(crawl_path) if crawl_path.exists() else pd.DataFrame()

    lines = ["# SEO Snapshot", ""]
    if not opp.empty:
        target = opp[opp["intent"] != "other"]
        lines += [
            f"- Search Console query/page rows: **{len(opp):,}**",
            f"- Rows matching target/local intent: **{len(target):,}**",
            "",
            "## Highest-priority query/page opportunities",
            "",
        ]
        cols = ["query", "page", "clicks", "impressions", "ctr", "position", "intent", "opportunity_type", "priority_score"]
        top = target[cols].head(25)
        lines.append(top.to_markdown(index=False) if not top.empty else "_No target queries found in this window._")
    else:
        lines.append("- No Search Console query/page data was returned.")

    lines += ["", "## Crawl quick checks", ""]
    if not crawl.empty:
        html = crawl[crawl.get("status", pd.Series(dtype=str)).astype(str).eq("200")] if "status" in crawl else crawl
        if "content_type" in html:
            html = html[html["content_type"].fillna("").str.contains("text/html", case=False)]
        if "final_url" in html:
            html = html[~html["final_url"].fillna("").str.lower().str.split("?").str[0].str.endswith((".kml", ".xml"))]
        lines += [
            f"- Crawled rows: **{len(crawl):,}**",
            f"- 200 HTML response rows (including redirects/templates): **{len(html):,}**",
        ]
        if "title" in html:
            lines.append(f"- Missing titles: **{int(html['title'].fillna('').eq('').sum()):,}**")
        if "meta_description" in html:
            lines.append(f"- Missing meta descriptions: **{int(html['meta_description'].fillna('').eq('').sum()):,}**")
        if "h1" in html:
            lines.append(f"- Missing H1s: **{int(html['h1'].fillna('').eq('').sum()):,}**")
        if "text_mentions_adhd" in crawl:
            lines.append(f"- Pages mentioning ADHD: **{int(crawl['text_mentions_adhd'].fillna(False).sum()):,}**")
        if "text_mentions_paoli" in crawl:
            lines.append(f"- Pages mentioning Paoli: **{int(crawl['text_mentions_paoli'].fillna(False).sum()):,}**")
    else:
        lines.append("- No crawl data found.")

    lines += [
        "",
        "> This file is intentionally a mechanical summary. The Codex/LLM audit should interpret these files, inspect page content, and write the actual recommendations.",
        "",
    ]
    (reports_dir / "snapshot.md").write_text("\n".join(lines), encoding="utf-8")
