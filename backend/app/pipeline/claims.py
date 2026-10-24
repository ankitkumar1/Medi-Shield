"""Pull claim, prescription, and identity fields out of OCR text."""

import re
from datetime import datetime

DATE = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")
ICD = re.compile(r"\b([A-TV-Z]\d{2}(?:\.\d{1,4}[A-Z]?)?)\b")
NPI = re.compile(r"NPI[:\s-]*(\d{10})", re.I)
POLICY = re.compile(r"MED-GLD-\d{7}", re.I)
CLAIM_NO = re.compile(r"CLM-\d{4}-\d{5}", re.I)
MONEY = re.compile(r"\$?\s*(\d{1,3}(?:,\d{3})*\.\d{2})")
CPT = re.compile(r"\b(\d{5})\b")
SKIP_CPT = {"00000"}


def _dates(text: str) -> list[datetime]:
    found = []
    for raw in DATE.findall(text):
        try:
            found.append(datetime.strptime(raw, "%m/%d/%Y"))
        except ValueError:
            continue
    return found


def _money(text: str) -> list[float]:
    values = []
    for raw in MONEY.findall(text):
        try:
            values.append(float(raw.replace(",", "")))
        except ValueError:
            continue
    return values


def _cpts(text: str) -> list[str]:
    codes = []
    for code in CPT.findall(text):
        number = int(code)
        if number < 10000 or code in SKIP_CPT:
            continue
        # Years and zip-like values are not procedure codes.
        if 1900 <= number <= 2099:
            continue
        if code not in codes:
            codes.append(code)
    return codes


def _icds(text: str) -> list[str]:
    codes = []
    for code in ICD.findall(text.upper()):
        if code not in codes:
            codes.append(code)
    return codes


def extract_fields(text: str, doc_type: str) -> dict:
    dates = _dates(text)
    amounts = _money(text)
    policy = POLICY.search(text)
    npi = NPI.search(text)
    claim_number = CLAIM_NO.search(text)
    upper = text.upper()
    missing_markers = any(
        marker in upper
        for marker in (
            "MISSING",
            "ILLEGIBLE",
            "DIAGNOSIS CODE MISSING",
            "DRUG NAME MISSING",
        )
    )
    service_dates = [item for item in dates if item.year >= 2024]
    dob_dates = [item for item in dates if item.year < 2010]
    expiry_dates = [item for item in dates if item.year >= 2020]

    fields = {
        "policy_number": policy.group(0).upper() if policy else None,
        "npi": f"NPI-{npi.group(1)}" if npi else None,
        "claim_number": claim_number.group(0).upper() if claim_number else None,
        "icd10": _icds(text),
        "cpt": _cpts(text),
        "amounts": amounts,
        "billed_amount": max(amounts) if amounts else None,
        "service_date": service_dates[0].strftime("%m/%d/%Y") if service_dates else None,
        "date_of_birth": dob_dates[0].strftime("%m/%d/%Y") if dob_dates else None,
        "expiry_dates": [item.strftime("%m/%d/%Y") for item in expiry_dates],
        "says_expired": "EXPIRED" in upper,
        "missing_marker": missing_markers,
        "raw_upper": upper,
        "dates": [item.strftime("%m/%d/%Y") for item in dates],
    }

    if doc_type == "CLAIM_FORM":
        required = {
            "billed_amount": fields["billed_amount"],
            "icd10": fields["icd10"],
            "cpt": fields["cpt"],
            "npi": fields["npi"],
            "service_date": fields["service_date"],
        }
        errors = [name for name, value in required.items() if not value]
        if missing_markers:
            errors.append("missing_marker_on_form")
        fields["schema_valid"] = not errors
        fields["validation_errors"] = errors
    elif doc_type == "PRESCRIPTION":
        errors = []
        if missing_markers or not re.search(r"[A-Za-z]{4,}", text):
            errors.append("incomplete_prescription")
        if "DRUG NAME MISSING" in upper or "ILLEGIBLE" in upper:
            errors.append("missing_marker_on_form")
        fields["schema_valid"] = not errors
        fields["validation_errors"] = errors
    else:
        fields["schema_valid"] = True
        fields["validation_errors"] = []

    fields["confidence"] = 0.86 if fields["schema_valid"] else 0.7
    return fields
