"""Final Approve / Reject / Escalate rule.

1. Unknown document, or classifier confidence under 0.6 → ESCALATE
2. Fraud score at least 0.3 → ESCALATE
3. KYC failed, claim schema invalid, or procedure not covered → REJECT
4. Otherwise → APPROVE
"""


def orchestrate(doc_type: str, classifier: dict, kyc: dict, claims: dict, policy: dict, fraud: dict) -> dict:
    reasons: list[str] = []
    if doc_type == "UNKNOWN" or classifier.get("confidence", 0) < 0.6:
        reasons.append(classifier.get("reason") or "low_confidence")
        decision = "ESCALATE"
    elif fraud.get("fraud_score", 0) >= 0.3:
        reasons.extend(fraud.get("anomalies") or ["fraud"])
        decision = "ESCALATE"
    elif doc_type == "ID_DOCUMENT" and not kyc.get("kyc_passed", True):
        reasons.extend(kyc.get("flags") or ["kyc_failed"])
        decision = "REJECT"
    elif doc_type in {"CLAIM_FORM", "PRESCRIPTION"} and not claims.get("schema_valid", True):
        reasons.extend(claims.get("validation_errors") or ["schema_invalid"])
        decision = "REJECT"
    elif doc_type == "CLAIM_FORM" and not policy.get("covered", True):
        reasons.append("procedure_not_covered")
        decision = "REJECT"
    else:
        reasons.append("kyc_passed_claim_valid_covered_low_fraud")
        decision = "APPROVE"

    confidences = [
        classifier.get("confidence"),
        kyc.get("confidence"),
        claims.get("confidence"),
        policy.get("confidence"),
        fraud.get("confidence"),
    ]
    present = [value for value in confidences if isinstance(value, (int, float))]
    confidence = round(sum(present) / len(present), 2) if present else 0.5
    if decision == "ESCALATE" and classifier.get("confidence", 1) < 0.6:
        confidence = min(confidence, classifier["confidence"])

    return {
        "decision": decision,
        "confidence": confidence,
        "justification": _sentence(decision, reasons),
        "reasons": reasons,
    }


def _sentence(decision: str, reasons: list[str]) -> str:
    detail = ", ".join(reasons) if reasons else "the specialist checks"
    if decision == "APPROVE":
        return "Approved. Identity, claim fields, coverage, and fraud score are within the auto-approve limits."
    if decision == "REJECT":
        return f"Rejected because {detail}."
    return f"Escalated for a reviewer because {detail}."
