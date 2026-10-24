"""Turn generator metadata and render facts into field-level gold labels.

Decision order, agreed for this project:
1. Unknown, blurry, or tampered → ESCALATE
2. Fraud label → ESCALATE
3. Expired ID, missing fields, or uncovered procedure → REJECT
4. Otherwise → APPROVE
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data" / "dataset"
GOLD_PATH = ROOT / "data" / "gold" / "gold.json"

DOC_TYPE = {
    "claim_forms": "CLAIM_FORM",
    "id_documents": "ID_DOCUMENT",
    "discharge_summaries": "DISCHARGE_SUMMARY",
    "prescriptions": "PRESCRIPTION",
    "policy_amendments": "POLICY_AMENDMENT",
    "unknown": "UNKNOWN",
}


def decide(meta):
    flags = set(meta.get("edge_flags") or [])
    reasons = []
    if meta.get("category") == "unknown":
        reasons.append("unknown_document")
    if meta.get("blur_simulated"):
        reasons.append("blurry_scan")
    if "tampered_id" in flags:
        reasons.append("tampered_id")
    if meta.get("fraud_label"):
        reasons.append(meta.get("fraud_reason") or "fraud")
    if "expired_id" in flags:
        reasons.append("expired_id")
    if "missing_fields" in flags:
        reasons.append("missing_fields")
    if "uncovered_procedure" in flags:
        reasons.append("uncovered_procedure")

    if meta.get("category") == "unknown" or meta.get("blur_simulated") or "tampered_id" in flags:
        decision = "ESCALATE"
    elif meta.get("fraud_label"):
        decision = "ESCALATE"
    elif flags & {"expired_id", "missing_fields", "uncovered_procedure"}:
        decision = "REJECT"
    else:
        decision = "APPROVE"
    return decision, reasons


def rel(path):
    p = Path(path)
    try:
        return str(p.resolve().relative_to(ROOT))
    except ValueError:
        return str(p)


def visible_fields(meta, fact):
    """Fields an extractor should recover from this file. None means the field is blank on the page."""
    if fact is None:
        return {}
    category = meta["category"]
    missing = fact.get("missing_field_type")
    rx_missing = fact.get("rx_missing_field_type")
    claim_missing = "missing_fields" in (meta.get("edge_flags") or []) and category == "claim_forms"
    rx_gap = "missing_fields" in (meta.get("edge_flags") or []) and category == "prescriptions"

    name = fact["id_display_name"] if category == "id_documents" else fact["name"]
    base = {
        "patient_name": name,
        "date_of_birth": None if (claim_missing and missing == "dob") else fact["dob"],
        "policy_number": fact["policy_number"],
        "npi": None if claim_missing else fact["npi"],
        "provider_name": fact["doctor"],
        "icd10": [] if (claim_missing and missing == "diag_code") else [fact["icd10_primary"], fact["icd10_secondary"]],
        "cpt": fact["cpt"],
        "service_date": fact["treatment_date"],
        "billed_amount": round(sum(item["charge"] for item in fact["cpt"]), 2),
    }

    if category == "claim_forms":
        if fact["claim_form_type"] == "UB04" and fact.get("ub04"):
            base["service_date"] = fact["ub04"]["admit_date"]
            base["discharge_date"] = fact["ub04"]["discharge_date"]
            base["billed_amount"] = fact["ub04"]["billed_amount"]
        elif fact.get("cms1500"):
            base["billed_amount"] = fact["cms1500"]["billed_amount"]
            # CMS-1500 box 21 prints the primary diagnosis only.
            if not (claim_missing and missing == "diag_code"):
                base["icd10"] = [fact["icd10_primary"]]
        base["claim_number"] = fact["claim_number"]
        if claim_missing and missing == "diag_code":
            base["icd10"] = []
        return base

    if category == "id_documents":
        shows_expiry_date = fact["id_type"] != "medicare_card"
        return {
            "patient_name": fact["id_display_name"],
            "date_of_birth": fact["dob"],
            "policy_number": None if fact["id_type"] == "medicare_card" else fact["policy_number"],
            "id_expiry": fact.get("id_expiry") if shows_expiry_date else None,
            "expired_banner": fact["id_type"] == "medicare_card" and "expired_id" in (meta.get("edge_flags") or []),
            "id_type": fact["id_type"],
            "gender": fact["gender"],
        }

    if category == "discharge_summaries":
        rendered = fact.get("discharge") or {}
        base["service_date"] = rendered.get("admit_date", fact["treatment_date"])
        base["discharge_date"] = rendered.get("discharge_date")
        base["length_of_stay_days"] = rendered.get("length_of_stay_days")
        return base

    if category == "prescriptions":
        drugs = fact["prescriptions"]
        if rx_gap and rx_missing == "drug_name":
            drugs = []
        elif rx_gap and rx_missing == "dosage":
            drugs = [{**drug, "sig": None} for drug in drugs]
        return {
            "patient_name": fact["name"],
            "date_of_birth": fact["dob"],
            "policy_number": fact["policy_number"],
            "npi": fact["npi"],
            "provider_name": fact["doctor"],
            "rx_date": fact.get("rx_date"),
            "icd10": [fact["icd10_primary"]],
            "drugs": drugs,
            "missing_rx_field": rx_missing if rx_gap else None,
        }

    if category == "policy_amendments":
        return {
            "patient_name": fact["name"],
            "date_of_birth": fact["dob"],
            "policy_number": fact["policy_number"],
            "amendment_type": fact["amendment_type"],
            "handwritten": fact["amendment_handwritten"],
        }

    return {}


def build():
    metadata = json.loads((DATASET / "metadata.json").read_text())
    facts = {row["patient_id"]: row for row in json.loads((DATASET / "render_facts.json").read_text())}

    documents = []
    for meta in metadata:
        fact = facts.get(meta.get("patient_id"))
        decision, reasons = decide(meta)
        notes = []
        score = True
        if (
            meta.get("category") == "claim_forms"
            and fact
            and fact.get("fraud_reason") == "amount_under_10k"
            and fact.get("claim_form_type") == "UB04"
            and meta.get("fraud_label")
        ):
            notes.append(
                "Labeled amount_under_10k, but the $9,875 line is only drawn on CMS-1500. "
                "This UB-04 total is room and board plus CPT charges. Leave this file out of the decision score."
            )
            score = False
        if meta.get("doc_id", "").endswith("_dup"):
            notes.append("Duplicate of the original claim file. Fraud label applies only to this copy.")

        documents.append(
            {
                "doc_id": meta["doc_id"],
                "file_path": rel(meta["file_path"]),
                "category": meta["category"],
                "doc_type": DOC_TYPE[meta["category"]],
                "case_cluster_id": meta.get("case_cluster_id"),
                "patient_id": meta.get("patient_id"),
                "policy_number": meta.get("policy_number"),
                "expected_decision": decision,
                "decision_reasons": reasons,
                "fraud_label": meta.get("fraud_label", False),
                "fraud_reason": meta.get("fraud_reason"),
                "edge_flags": meta.get("edge_flags") or [],
                "blur_simulated": bool(meta.get("blur_simulated")),
                "include_in_decision_score": score,
                "notes": notes,
                "visible_fields": visible_fields(meta, fact),
                "episode": None
                if fact is None
                else {
                    "claim_number": fact["claim_number"],
                    "treatment_date": fact["treatment_date"],
                    "icd10": [fact["icd10_primary"], fact["icd10_secondary"]],
                    "cpt": fact["cpt"],
                    "npi": fact["npi"],
                    "provider_name": fact["doctor"],
                    "hospital": fact["hospital"],
                    "billed_amount": (fact.get("cms1500") or fact.get("ub04") or {}).get("billed_amount")
                    or round(sum(item["charge"] for item in fact["cpt"]), 2),
                },
            }
        )

    members = [
        {
            "patient_id": fact["patient_id"],
            "cluster_id": fact["cluster_id"],
            "name": fact["name"],
            "date_of_birth": fact["dob"],
            "gender": fact["gender"],
            "address": fact["address"],
            "ssn": fact["ssn"],
            "policy_number": fact["policy_number"],
            "group_number": fact["group_number"],
            "plan": "GOLD",
        }
        for fact in facts.values()
    ]

    gold = {
        "decision_rule": [
            "Unknown, blurry, or tampered document → ESCALATE",
            "Fraud label → ESCALATE",
            "Expired ID, missing fields, or uncovered procedure → REJECT",
            "Otherwise → APPROVE",
        ],
        "document_count": len(documents),
        "member_count": len(members),
        "documents": documents,
        "members": members,
    }
    GOLD_PATH.parent.mkdir(parents=True, exist_ok=True)
    GOLD_PATH.write_text(json.dumps(gold, indent=2))
    return gold


if __name__ == "__main__":
    gold = build()
    from collections import Counter

    counts = Counter(doc["expected_decision"] for doc in gold["documents"])
    print(f"Wrote {GOLD_PATH}")
    print(f"documents={gold['document_count']} members={gold['member_count']} decisions={dict(counts)}")
