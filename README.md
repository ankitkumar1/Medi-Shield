# Medi-Shield

AI document intake for MediShield Health Insurance. One uploaded file becomes a case. A classifier routes it, specialist agents extract and check it, and an orchestrator returns Approve, Reject, or Escalate.

This repository is the implementation. The assignment brief and document generators live in the parent folder.

## Layout

```
backend/     FastAPI API and, later, the LangGraph agents
frontend/    Next.js case-management UI (next step)
data/        Local document storage (gitignored)
```

## Run the API

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env
uvicorn app.main:app --reload --app-dir .
```

Open http://127.0.0.1:8000/health. You should see `{"status":"ok","env":"local"}`.

## Sprints

Each sprint ends with a check. The next sprint starts only after that check passes.

| Sprint | Work | Done when |
|---|---|---|
| 1. Foundation | API skeleton, gitignore, env example | `GET /health` returns `{"status":"ok"}`. **Verified.** |
| 2. Dataset and gold labels | Generate the synthetic documents. Save field-level gold and an expected decision for every file. | 155 documents on disk. Gold file includes ICD, CPT, amount, NPI, dates, and `expected_decision`. Three sample images match their labels. |
| 3. Ingestion | Upload endpoint, `case_id`, local storage, list and fetch a case | One PNG uploaded with curl is stored and returned by the case APIs. |
| 4. Classifier | Vision model labels the six document types. Low confidence goes to review. | One file of each type is classified correctly. |
| 5. Claims extraction | Pull amount, ICD-10, CPT, NPI, and service date. Validate the schema. | Five claim forms, including one missing-field form, match the gold file. |
| 6. KYC | Match name, date of birth, and policy number. Check expiry and tamper. | Expired ID fails. Expiring-soon ID passes. Name mismatch is flagged. A clean ID passes. |
| 7. Policy RAG | Ingest the Gold and Silver PDFs. Retrieve the clause for a procedure code. | An excluded CPT is not covered and cites the exclusion. CPT 99213 is covered and cites coinsurance. |
| 8. Decision pipeline | Fraud scoring, LangGraph wiring, orchestrator | A small set of known fraud, reject, and approve files matches `expected_decision`. |
| 9. Case UI | Dashboard, case detail, human override, audit log | Those four screens work in the browser. |
| 10. Evaluation | Stratified 20-document scorecard, architecture diagram, walkthrough | Decision correctness is at least 60%, and the weighted score is at least 70%. |

Decision priority, used when writing gold labels in Sprint 2:

1. Unknown document, or any agent confidence under 0.6 → **Escalate**
2. Fraud score at least 0.3 → **Escalate**
3. KYC failed, schema invalid, or procedure not covered → **Reject**
4. Otherwise → **Approve**

## GitHub

This repo stays local until you commit and push. `.env` is ignored.
