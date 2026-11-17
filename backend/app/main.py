from __future__ import annotations
"""
FastAPI Backend Service (`fastapi==0.163.1` compatible, backwards-compatible with 0.92+).
Exposes E2E endpoints for Authentication, Policy RAG Lookup, LangGraph Claim Intake,
Human-in-the-Loop (HITL) Checkpoint Resumption, Cryptographic Audit Verification,
and Golden Evaluation Suite execution.
"""
from typing import Any, Dict, Optional
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from .auth import SEED_USERS, authenticate_user, verify_jwt_token
from .config import SUPPORTED_2026_MODELS, DEPRECATED_GROQ_MODEL_MAP, settings
from .database import ClaimDatabase
from .evals.eval_runner import run_evaluation_suite
from .graph import execute_claim_pipeline, resume_claim_after_hitl
from .policy_rag import MASTER_POLICIES, retrieve_relevant_clauses
from .schemas import ClaimIntakeRequest, HITLDecisionInput, to_dict

app = FastAPI(
    title="Claimwise — Insurance Claims API",
    version="1.0.0",
    description="LangGraph-orchestrated claims workflow with optional Groq extraction, deterministic policy and settlement rules, and FastAPI.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db = ClaimDatabase()


def require_roles(*roles: str):
    """Enforce authentication and role authorization at the HTTP boundary."""
    def dependency(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="Missing Bearer token")
        payload = verify_jwt_token(authorization.split(" ", 1)[1].strip())
        if not payload:
            raise HTTPException(status_code=401, detail="Invalid or expired JWT token")
        if roles and payload.get("role") not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return payload
    return dependency


class LoginRequest(BaseModel):
    email: str
    password: str


@app.get("/api/v1/health")
def health_check() -> Dict[str, Any]:
    audit_status = db.verify_audit_chain()
    return {
        "status": "ok",
        "service": "claimwise-api",
        "version": "1.0.0",
        "primary_model": settings.primary_model,
        "reasoning_model": settings.reasoning_model,
        "triage_model": settings.triage_model,
        "groq_key_configured": bool(settings.groq_api_key),
        "inference_mode": "LIVE_GROQ_CONFIGURED" if settings.groq_api_key else "DETERMINISTIC_DEMO",
        "supported_2026_models": SUPPORTED_2026_MODELS,
        "deprecated_model_redirects": DEPRECATED_GROQ_MODEL_MAP,
        "audit_chain_integrity": audit_status,
    }


@app.post("/api/v1/auth/login")
def login(req: LoginRequest) -> Dict[str, Any]:
    auth = authenticate_user(req.email, req.password)
    if not auth:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    db.append_audit_event(
        claim_id="AUTH-SESSION",
        event_type="USER_LOGIN",
        actor=auth["user"]["full_name"],
        summary=f"Authenticated as {auth['user']['role']} ({auth['user']['email']})",
    )
    return auth


@app.get("/api/v1/auth/me")
def get_current_user(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization.split(" ", 1)[1].strip()
    payload = verify_jwt_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired JWT token")
    return payload


@app.get("/api/v1/policies", dependencies=[Depends(require_roles("officer", "policyholder", "siu_investigator"))])
def list_policies(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    policies = list(MASTER_POLICIES.values())
    if isinstance(authorization, str) and authorization.lower().startswith("bearer "):
        actor = verify_jwt_token(authorization.split(" ", 1)[1].strip()) or {}
        if actor.get("role") == "policyholder":
            policies = [p for p in policies if p.get("holder_email", "").lower() == actor.get("email", "").lower()]
    return {"policies": policies}


@app.get("/api/v1/policies/{policy_id}/clauses", dependencies=[Depends(require_roles("officer", "policyholder", "siu_investigator"))])
def search_policy_clauses(policy_id: str, q: str = "", authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    if isinstance(authorization, str) and authorization.lower().startswith("bearer "):
        actor = verify_jwt_token(authorization.split(" ", 1)[1].strip()) or {}
        policy = MASTER_POLICIES.get(policy_id, {})
        if actor.get("role") == "policyholder" and policy.get("holder_email", "").lower() != actor.get("email", "").lower():
            raise HTTPException(status_code=403, detail="You can only access your own policies")
    clauses = retrieve_relevant_clauses(policy_id, q, [])
    if not clauses:
        raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")
    return {"policy_id": policy_id, "query": q, "clauses": clauses}


@app.get("/api/v1/claims", dependencies=[Depends(require_roles("officer", "policyholder", "siu_investigator"))])
def get_all_claims(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    claims = db.list_claims()
    if not isinstance(authorization, str):
        authorization = None
    if authorization and authorization.lower().startswith("bearer "):
        actor = verify_jwt_token(authorization.split(" ", 1)[1].strip()) or {}
        if actor.get("role") == "policyholder":
            claims = [c for c in claims if c.get("intake", {}).get("claimant_email", "").lower() == actor.get("email", "").lower()]
    return {"count": len(claims), "claims": claims}


@app.get("/api/v1/claims/{claim_id}", dependencies=[Depends(require_roles("officer", "policyholder", "siu_investigator"))])
def get_single_claim(claim_id: str, authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    claim = db.get_claim(claim_id)
    if not isinstance(authorization, str):
        authorization = None
    if authorization and authorization.lower().startswith("bearer "):
        actor = verify_jwt_token(authorization.split(" ", 1)[1].strip()) or {}
        if actor.get("role") == "policyholder" and claim and claim.get("intake", {}).get("claimant_email", "").lower() != actor.get("email", "").lower():
            raise HTTPException(status_code=403, detail="You can only access your own claims")
    if not claim:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")
    return claim


@app.post("/api/v1/claims/submit", dependencies=[Depends(require_roles("officer", "policyholder"))])
def submit_new_claim(req: ClaimIntakeRequest, authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    payload = to_dict(req)
    if not isinstance(authorization, str):
        authorization = None
    if authorization and authorization.lower().startswith("bearer "):
        actor = verify_jwt_token(authorization.split(" ", 1)[1].strip()) or {}
        if actor.get("role") == "policyholder":
            policy = MASTER_POLICIES.get(payload.get("policy_id", ""), {})
            if payload.get("claimant_email", "").lower() != actor.get("email", "").lower() or policy.get("holder_email", "").lower() != actor.get("email", "").lower():
                raise HTTPException(status_code=403, detail="Policyholders can only submit claims against their own policies")
    cid = payload.get("claim_id") or f"CLM-2026-{len(db.list_claims()) + 801}"
    state = execute_claim_pipeline(payload, claim_id=cid)
    db.save_claim_state(state, actor=payload.get("claimant_name", "Policyholder"))
    return state


@app.post("/api/v1/claims/{claim_id}/hitl-decision", dependencies=[Depends(require_roles("officer"))])
def submit_hitl_decision(claim_id: str, decision: HITLDecisionInput) -> Dict[str, Any]:
    existing = db.get_claim(claim_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")
    updated = resume_claim_after_hitl(existing, to_dict(decision))
    db.save_claim_state(updated, actor=decision.officer_name)
    return updated


@app.get("/api/v1/audit", dependencies=[Depends(require_roles("officer", "siu_investigator"))])
def get_audit_trail() -> Dict[str, Any]:
    return {
        "verification": db.verify_audit_chain(),
        "events": db.list_audit_events(limit=100),
    }


@app.post("/api/v1/evals/run", dependencies=[Depends(require_roles("officer"))])
def trigger_eval_suite() -> Dict[str, Any]:
    return run_evaluation_suite()

