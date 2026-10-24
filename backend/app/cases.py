import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.config import ROOT, settings
from app.db import add_audit, audit_for, connect
from app.pipeline.graph import run_intake
from app.schemas import AuditEntry, CaseDetail, CaseList, CaseSummary, OverrideRequest

router = APIRouter(tags=["cases"])

ALLOWED = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".pdf": "application/pdf",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
}

STATUS = {"APPROVE": "APPROVED", "REJECT": "REJECTED", "ESCALATE": "ESCALATED"}


def _summary(row: sqlite3.Row) -> CaseSummary:
    case_id = row["case_id"]
    return CaseSummary(
        case_id=case_id,
        original_filename=row["original_filename"],
        content_type=row["content_type"],
        size_bytes=row["size_bytes"],
        status=row["status"],
        created_at=row["created_at"],
        file_url=f"/cases/{case_id}/file",
        doc_type=row["doc_type"],
        decision=row["decision"],
        confidence=row["confidence"],
        justification=row["justification"],
    )


def _get_row(case_id: str) -> sqlite3.Row:
    with connect() as connection:
        row = connection.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return row


def _detail(row: sqlite3.Row) -> CaseDetail:
    agents = json.loads(row["agents_json"]) if row["agents_json"] else {}
    audit = [
        AuditEntry(
            created_at=item["created_at"],
            actor=item["actor"],
            action=item["action"],
            detail=item["detail"],
        )
        for item in audit_for(row["case_id"])
    ]
    return CaseDetail(**_summary(row).model_dump(), agents=agents, audit=audit)


def process_case(case_id: str) -> CaseDetail:
    row = _get_row(case_id)
    path = ROOT / row["stored_path"]
    result = run_intake(str(path), row["original_filename"])
    decision = result["decision"]
    with connect() as connection:
        connection.execute(
            """
            UPDATE cases
            SET doc_type = ?, decision = ?, confidence = ?, justification = ?,
                agents_json = ?, status = ?
            WHERE case_id = ?
            """,
            (
                result["doc_type"],
                decision,
                result["confidence"],
                result["justification"],
                json.dumps(result["agents"]),
                STATUS.get(decision, "ESCALATED"),
                case_id,
            ),
        )
    add_audit(
        case_id,
        "pipeline",
        "DECIDED",
        f"{decision} ({result['doc_type']}) — {result['justification']}",
    )
    return _detail(_get_row(case_id))


@router.post("/cases", response_model=CaseDetail, status_code=201)
async def create_case(file: UploadFile) -> CaseDetail:
    filename = Path(file.filename or "").name
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED:
        raise HTTPException(status_code=415, detail="Upload a JPEG, PNG, PDF, or TIFF document.")

    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    case_id = f"case_{uuid4().hex[:12]}"
    case_dir = settings.storage_dir / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    stored = case_dir / filename
    stored.write_bytes(payload)

    created_at = datetime.now(timezone.utc).isoformat()
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO cases (
                case_id, original_filename, content_type, stored_path,
                size_bytes, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                case_id,
                filename,
                ALLOWED[suffix],
                str(stored.resolve().relative_to(ROOT)),
                len(payload),
                "PROCESSING",
                created_at,
            ),
        )
    add_audit(case_id, "intake", "RECEIVED", f"Stored {filename} ({len(payload)} bytes).")
    return process_case(case_id)


@router.get("/cases", response_model=CaseList)
def list_cases() -> CaseList:
    with connect() as connection:
        rows = connection.execute("SELECT * FROM cases ORDER BY created_at DESC").fetchall()
    return CaseList(cases=[_summary(row) for row in rows])


@router.get("/review", response_model=CaseList)
def review_queue() -> CaseList:
    with connect() as connection:
        rows = connection.execute(
            "SELECT * FROM cases WHERE decision = 'ESCALATE' OR status = 'ESCALATED' ORDER BY created_at DESC"
        ).fetchall()
    return CaseList(cases=[_summary(row) for row in rows])


@router.get("/cases/{case_id}", response_model=CaseDetail)
def get_case(case_id: str) -> CaseDetail:
    return _detail(_get_row(case_id))


@router.post("/cases/{case_id}/process", response_model=CaseDetail)
def rerun_case(case_id: str) -> CaseDetail:
    return process_case(case_id)


@router.post("/cases/{case_id}/override", response_model=CaseDetail)
def override_case(case_id: str, body: OverrideRequest) -> CaseDetail:
    decision = body.decision.upper()
    if decision not in STATUS:
        raise HTTPException(status_code=400, detail="Decision must be APPROVE, REJECT, or ESCALATE.")
    row = _get_row(case_id)
    note = body.note.strip() or "Reviewer override."
    with connect() as connection:
        connection.execute(
            "UPDATE cases SET decision = ?, status = ?, justification = ? WHERE case_id = ?",
            (decision, STATUS[decision], note, case_id),
        )
    add_audit(case_id, body.actor, "OVERRIDE", f"{row['decision']} → {decision}. {note}")
    return _detail(_get_row(case_id))


@router.get("/cases/{case_id}/file")
def get_case_file(case_id: str) -> FileResponse:
    row = _get_row(case_id)
    path = ROOT / row["stored_path"]
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Stored file is missing")
    return FileResponse(path, media_type=row["content_type"], filename=row["original_filename"])
