"""Lossless conversions between guided rows and validated site settings."""
from __future__ import annotations

import math

from .config import BASE_RULES, PSYCHOLOGY_RULES, Phrase, RuleOverride


def text_cell(value):
    if value is None or isinstance(value, float) and math.isnan(value):
        return ""
    if not isinstance(value, str):
        raise ValueError("Use text in the list fields.")
    return value if value.strip() else ""


def service_rows(groups):
    return [{"Service group": group, "Related search term": term}
            for group, terms in groups.items() for term in (terms or [""])]


def services_from_rows(rows):
    groups = {}
    for row in rows:
        group, term = text_cell(row.get("Service group")), text_cell(row.get("Related search term"))
        if not group and not term:
            continue
        if not group:
            raise ValueError("Give each related search term a service group.")
        terms = groups.setdefault(group, [])
        if term:
            if term in terms:
                raise ValueError("A related search term is repeated within its service group.")
            terms.append(term)
    return groups


def facts_from_rows(rows):
    facts = {}
    for row in rows:
        name, value = text_cell(row.get("Fact")), text_cell(row.get("Confirmed value"))
        if not name and not value:
            continue
        if not name or not value:
            raise ValueError("Each confirmed fact needs both a name and a value.")
        if name in facts:
            raise ValueError("Each fact name must be unique.")
        facts[name] = value
    return facts


def rule_rows(config):
    registry = {**BASE_RULES, **(PSYCHOLOGY_RULES if config.industry == "psychology" else {})}
    rows = []
    for name, rule in registry.items():
        settings = {**rule["settings"], **(config.overrides[name].model_dump(exclude_none=True) if name in config.overrides else {})}
        rows.append({"Rule": name, "Enabled": settings["enabled"], "Minimum impressions": settings.get("min_impressions"),
                     "CTR threshold (%)": settings["ctr_threshold"] * 100 if "ctr_threshold" in settings else None})
    return rows


def overrides_from_rows(rows, config):
    registry = {**BASE_RULES, **(PSYCHOLOGY_RULES if config.industry == "psychology" else {})}
    overrides, seen = {}, set()
    for row in rows:
        name = row["Rule"]
        if name not in registry or name in seen:
            raise ValueError("Keep the existing rule names and one row per rule.")
        seen.add(name)
        defaults = registry[name]["settings"]
        values = {"enabled": row["Enabled"]}
        for label, key in (("Minimum impressions", "min_impressions"), ("CTR threshold (%)", "ctr_threshold")):
            value = row.get(label)
            missing = value is None or isinstance(value, float) and math.isnan(value)
            if key not in defaults:
                if not missing:
                    raise ValueError("This rule does not use " + label.lower() + ". Leave that cell empty.")
                continue
            if missing or isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError("Supply a valid number for " + label.lower() + ".")
            if key == "min_impressions":
                if int(value) != value:
                    raise ValueError("Minimum impressions must be a whole number.")
                value = int(value)
            else:
                value = float(value) / 100
            values[key] = value
        changed = {key: value for key, value in values.items() if value != defaults[key]}
        if changed:
            overrides[name] = RuleOverride.model_validate(changed)
    if seen != set(registry):
        raise ValueError("Keep every audit rule in the options table.")
    return overrides


def phrase_rows(phrases):
    return [{**p.model_dump(), "related_terms": "\n".join(p.related_terms)} for p in phrases]


def phrases_from_rows(rows):
    phrases = []
    for row in rows:
        value = {k: row.get(k) for k in Phrase.model_fields}
        if not text_cell(value["phrase"]) and all(not text_cell(value[k]) for k in ("group", "location", "landing_page", "related_terms")):
            continue
        for key in ("phrase", "group", "location", "landing_page"):
            value[key] = text_cell(value[key])
        value["group"] = value["group"] or "service"
        value["related_terms"] = [text_cell(t) for t in text_cell(value["related_terms"]).splitlines() if text_cell(t)]
        if value["priority"] is None or isinstance(value["priority"], float) and math.isnan(value["priority"]):
            value["priority"] = 3
        elif isinstance(value["priority"], float) and value["priority"].is_integer():
            value["priority"] = int(value["priority"])
        if value["active"] is None:
            value["active"] = True
        phrases.append(Phrase.model_validate(value))
    return phrases
