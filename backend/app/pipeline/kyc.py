"""Identity checks against the member book."""

import re
from datetime import datetime

from app.pipeline.history import history_for_policy, member_by_policy


def _norm(value: str) -> str:
    return re.sub(r"[^A-Z]", "", value.upper())


def _first_last(name: str) -> tuple[str, str]:
    parts = [part for part in re.split(r"\s+", name.strip()) if part and part.strip(".")]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return _norm(parts[0]), ""
    return _norm(parts[0]), _norm(parts[1])


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _service_date(policy: str | None) -> datetime | None:
    dates = []
    for row in history_for_policy(policy):
        parsed = _parse(row.get("treatment_date"))
        if parsed:
            dates.append(parsed)
    return min(dates) if dates else None


def check_kyc(text: str, doc_type: str, fields: dict) -> dict:
    if doc_type not in {"ID_DOCUMENT", "CLAIM_FORM", "PRESCRIPTION", "DISCHARGE_SUMMARY", "POLICY_AMENDMENT"}:
        return {"kyc_passed": True, "flags": [], "confidence": 0.9, "member_name": None}

    policy = fields.get("policy_number")
    member = member_by_policy(policy)
    flags: list[str] = []
    upper = text.upper()

    if doc_type == "ID_DOCUMENT" and "EXPIRED" in upper:
        flags.append("expired_id")

    if doc_type == "ID_DOCUMENT" and member and "EXPIRED" not in upper:
        service = _service_date(policy)
        expiry_values = []
        for raw in fields.get("expiry_dates") or []:
            parsed = _parse(raw)
            if parsed and parsed.year >= 2020:
                expiry_values.append(parsed)
        if service and expiry_values and max(expiry_values) < service:
            flags.append("expired_id")

    name_mismatch = False
    if member and policy and _norm(member["name"]) not in _norm(text):
        member_first, member_last = _first_last(member["name"])
        text_norm = _norm(text)
        last_ok = bool(member_last and member_last in text_norm)
        # One-vowel substitutions still share most of the first name.
        first_close = False
        if member_first and last_ok:
            for index in range(len(member_first)):
                pattern = member_first[:index] + "." + member_first[index + 1 :]
                if re.search(pattern, text_norm):
                    first_close = True
                    break
        if last_ok and first_close and member_first not in text_norm:
            name_mismatch = True
            flags.append("name_mismatch")

    if doc_type == "ID_DOCUMENT" and policy and member is None:
        flags.append("policy_not_in_member_book")

    hard_fail = any(flag in flags for flag in ("expired_id", "policy_not_in_member_book"))
    return {
        "kyc_passed": not hard_fail,
        "flags": flags,
        "confidence": 0.55 if name_mismatch else (0.9 if not flags else 0.8),
        "member_name": member["name"] if member else None,
        "policy_number": policy,
    }
