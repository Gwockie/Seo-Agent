"""Synthetic evidence builders, never applied to real workspace records."""
from seo_agent import discovery as d
from seo_agent.discovery_models import ISOLATION


def staging_connection(store, sid, url, instance):
    production = next((c for c in d.connections(store, sid) if c["environment"] == "production" and c["enabled"]), None)
    if not production:
        pid = d.configure(store, sid, dict(label="Synthetic production", provider="Synthetic fixture provider", method="public",
            url=store.site(sid).url, environment="production", installation_id="synthetic"))
        production = d.connection(store, sid, pid)
    cid = d.configure(store, sid, dict(label="Synthetic staging", provider="Synthetic fixture provider", method="public",
        url=url, environment="staging", installation_id=instance))
    facts = [dict(area=area, result="isolated", production_resource="synthetic-production-" + area,
        environment_resource="synthetic-staging-" + area, observation="Synthetic independent provider resource observation",
        source_reference="Synthetic host record " + area) for area in ISOLATION]
    next(f for f in facts if f["area"] == "installation_identity").update(
        production_resource=production["installation_id"], environment_resource=instance)
    c = d.connection(store, sid, cid)
    d._save(store, sid, c, "administrator_export", {"host": facts}, certainty="administrator_asserted")
    d.review_isolation(store, sid, cid, human_clicked=True, source="Synthetic independently reviewed host evidence")
    return cid
