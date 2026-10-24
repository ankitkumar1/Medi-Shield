"""LangGraph intake: classify, specialists, fraud, then the orchestrator."""

from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.pipeline.classify import classify
from app.pipeline.claims import extract_fields
from app.pipeline.fraud import score_fraud
from app.pipeline.groq_vision import classify_image
from app.pipeline.kyc import check_kyc
from app.pipeline.ocr import blur_variance, read_text
from app.pipeline.orchestrator import orchestrate
from app.pipeline.policy import retrieve


class IntakeState(TypedDict, total=False):
    path: str
    source_name: str
    text: str
    blurry: bool
    classifier: dict
    claims: dict
    kyc: dict
    policy: dict
    fraud: dict
    orchestrator: dict


def _ocr(state: IntakeState) -> IntakeState:
    path = state["path"]
    text = read_text(path)
    blurry = blur_variance(path) < 700
    return {"text": text, "blurry": blurry}


def _classify(state: IntakeState) -> IntakeState:
    result = classify_image(state.get("path") or "")
    if result is None:
        result = classify(state.get("text") or "", state.get("blurry", False))
        result["provider"] = "local"
    elif state.get("blurry"):
        result["confidence"] = min(result["confidence"], 0.44)
        result["routing_tags"] = ["groq", "human_review", "blurry"]
    return {"classifier": result}


def _route(state: IntakeState) -> str:
    result = state.get("classifier") or {}
    if result.get("doc_type") == "UNKNOWN" or result.get("confidence", 0) < 0.6:
        return "orchestrate"
    return "specialists"


def _specialists(state: IntakeState) -> IntakeState:
    doc_type = state["classifier"]["doc_type"]
    text = state.get("text") or ""
    claims = extract_fields(text, doc_type)
    kyc = check_kyc(text, doc_type, claims)
    policy = retrieve(claims.get("cpt") or [], doc_type)
    return {"claims": claims, "kyc": kyc, "policy": policy}


def _fraud(state: IntakeState) -> IntakeState:
    doc_type = state["classifier"]["doc_type"]
    claims = state.get("claims") or {}
    claims = {**claims, "raw_upper": (state.get("text") or "").upper()}
    kyc = state.get("kyc") or {"flags": []}
    return {"fraud": score_fraud(doc_type, claims, kyc, state.get("source_name"))}


def _orchestrate(state: IntakeState) -> IntakeState:
    classifier = state.get("classifier") or {"doc_type": "UNKNOWN", "confidence": 0.2}
    doc_type = classifier.get("doc_type", "UNKNOWN")
    empty_claims = {"schema_valid": True, "validation_errors": [], "confidence": 0.9, "cpt": []}
    empty_kyc = {"kyc_passed": True, "flags": [], "confidence": 0.9}
    empty_policy = {"covered": True, "coverage_percentage": None, "policy_clause": "", "exclusions": [], "confidence": 0.9}
    empty_fraud = {"fraud_score": 0.0, "anomalies": [], "risk_level": "LOW", "confidence": 0.9}
    return {
        "orchestrator": orchestrate(
            doc_type,
            classifier,
            state.get("kyc") or empty_kyc,
            state.get("claims") or empty_claims,
            state.get("policy") or empty_policy,
            state.get("fraud") or empty_fraud,
        )
    }


def build_graph():
    graph = StateGraph(IntakeState)
    graph.add_node("ocr", _ocr)
    graph.add_node("classify", _classify)
    graph.add_node("specialists", _specialists)
    graph.add_node("fraud", _fraud)
    graph.add_node("orchestrate", _orchestrate)
    graph.set_entry_point("ocr")
    graph.add_edge("ocr", "classify")
    graph.add_conditional_edges("classify", _route, {"specialists": "specialists", "orchestrate": "orchestrate"})
    graph.add_edge("specialists", "fraud")
    graph.add_edge("fraud", "orchestrate")
    graph.add_edge("orchestrate", END)
    return graph.compile()


PIPELINE = build_graph()


def run_intake(path: str, source_name: str | None = None) -> dict:
    result = PIPELINE.invoke({"path": path, "source_name": source_name or path})
    orchestrator = result["orchestrator"]
    classifier = result.get("classifier") or {}
    return {
        "doc_type": classifier.get("doc_type", "UNKNOWN"),
        "decision": orchestrator["decision"],
        "confidence": orchestrator["confidence"],
        "justification": orchestrator["justification"],
        "agents": {
            "classifier": classifier,
            "kyc": result.get("kyc"),
            "claims": _public_claims(result.get("claims")),
            "policy": result.get("policy"),
            "fraud": result.get("fraud"),
            "orchestrator": orchestrator,
        },
    }


def _public_claims(claims: dict | None) -> dict | None:
    if not claims:
        return None
    hidden = {"raw_upper"}
    return {key: value for key, value in claims.items() if key not in hidden}
