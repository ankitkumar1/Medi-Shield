from pydantic import BaseModel, Field


class CaseSummary(BaseModel):
    case_id: str
    original_filename: str
    content_type: str
    size_bytes: int
    status: str
    created_at: str
    file_url: str
    doc_type: str | None = None
    decision: str | None = None
    confidence: float | None = None
    justification: str | None = None


class CaseList(BaseModel):
    cases: list[CaseSummary]


class AuditEntry(BaseModel):
    created_at: str
    actor: str
    action: str
    detail: str


class CaseDetail(CaseSummary):
    agents: dict = Field(default_factory=dict)
    audit: list[AuditEntry] = Field(default_factory=list)


class OverrideRequest(BaseModel):
    decision: str
    note: str = ""
    actor: str = "ops"
