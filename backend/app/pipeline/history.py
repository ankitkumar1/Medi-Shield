"""Member book and prior-claim history used by KYC and fraud.

Seeded from data/gold/gold.json. Duplicate copies (doc ids ending in _dup)
are not prior history; they are the submissions the fraud rule should catch.
"""

import json
from functools import lru_cache
from pathlib import Path

from app.config import ROOT

GOLD = ROOT / "data" / "gold" / "gold.json"


@lru_cache(maxsize=1)
def load_reference() -> dict:
    if not GOLD.is_file():
        return {"members": [], "history": []}
    gold = json.loads(GOLD.read_text())
    members = gold.get("members") or []
    history = []
    for doc in gold.get("documents") or []:
        if str(doc.get("doc_id", "")).endswith("_dup"):
            continue
        episode = doc.get("episode") or {}
        visible = doc.get("visible_fields") or {}
        history.append(
            {
                "doc_id": doc.get("doc_id"),
                "patient_id": doc.get("patient_id"),
                "doc_type": doc.get("doc_type"),
                "policy_number": doc.get("policy_number"),
                "claim_number": episode.get("claim_number"),
                "treatment_date": episode.get("treatment_date"),
                "name": visible.get("patient_name"),
                "rx_date": visible.get("rx_date"),
                "discharge_date": visible.get("discharge_date"),
                "admit_date": visible.get("service_date") if doc.get("doc_type") == "DISCHARGE_SUMMARY" else None,
            }
        )
    return {"members": members, "history": history}


def member_by_policy(policy: str | None) -> dict | None:
    if not policy:
        return None
    needle = policy.upper()
    for member in load_reference()["members"]:
        if str(member.get("policy_number", "")).upper() == needle:
            return member
    return None


def member_for_patient(patient_id: str | None) -> dict | None:
    if not patient_id:
        return None
    for member in load_reference()["members"]:
        if member.get("patient_id") == patient_id:
            return member
    return None


def history_for_policy(policy: str | None, skip_doc_id: str | None = None) -> list[dict]:
    if not policy:
        return []
    needle = policy.upper()
    rows = []
    for row in load_reference()["history"]:
        if str(row.get("policy_number", "")).upper() != needle:
            continue
        if skip_doc_id and row.get("doc_id") == skip_doc_id:
            continue
        rows.append(row)
    return rows
