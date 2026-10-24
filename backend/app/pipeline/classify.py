"""Classify a document from its OCR text."""

import re

RULES = [
    ("DISCHARGE_SUMMARY", ("DISCHARGE SUMMARY", "HOSPITAL COURSE", "DISCHARGE DISPOSITION")),
    ("CLAIM_FORM", ("HEALTH INSURANCE CLAIM FORM", "CMS-1500", "UB-04", "CMS-1450")),
    ("POLICY_AMENDMENT", ("POLICY AMENDMENT", "ENDORSEMENT REQUEST", "AMENDMENT TYPE")),
    ("PRESCRIPTION", ("PRESCRIPTION", "RX DATE", "DISPENSE AS WRITTEN", "SCHEDULE II")),
    ("ID_DOCUMENT", ("DRIVER", "PASSPORT", "MEDICARE", "STATE ID", "REAL ID", "HEALTH INSURANCE")),
]


def classify(text: str, blurry: bool) -> dict:
    upper = text.upper()
    letters = len(re.findall(r"[A-Za-z]", text))
    if letters < 40:
        return {
            "doc_type": "UNKNOWN",
            "confidence": 0.22,
            "routing_tags": ["human_review"],
            "reason": "Too little readable text to assign a document type.",
        }

    for doc_type, phrases in RULES:
        hits = [phrase for phrase in phrases if phrase in upper]
        if hits:
            confidence = 0.93 if not blurry else 0.44
            tags = ["auto"] if confidence >= 0.6 else ["human_review", "blurry"]
            return {
                "doc_type": doc_type,
                "confidence": confidence,
                "routing_tags": tags,
                "reason": f"Matched {hits[0]}.",
            }

    return {
        "doc_type": "UNKNOWN",
        "confidence": 0.48,
        "routing_tags": ["human_review"],
        "reason": "The page does not match a claim, identity, discharge, prescription, or amendment.",
    }
