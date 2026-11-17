from __future__ import annotations
"""
Typed Domain Schemas & LangGraph State Contract.
Designed for Pydantic v2 (2.12.3) with full compatibility fallback.
"""
from typing import Any, Dict, List, Optional, TypedDict
from pydantic import BaseModel, Field


def to_dict(model: BaseModel) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


class InvoiceLineItem(BaseModel):
    item_id: str = Field(..., description="Unique line item identifier, e.g. ITEM-01")
    description: str = Field(..., description="Billed service, procedure, or repair part")
    category: str = Field(
        ...,
        description="Category: room_rent | icu | surgery | pharmacy | consumables | diagnostics | parts | labor | surge_damage",
    )
    code: str = Field(default="N/A", description="ICD-10 / CPT / OEM part code")
    quantity: int = Field(default=1, ge=1)
    days: int = Field(default=1, ge=1)
    claimed_amount: float = Field(..., ge=0.0, description="Gross billed amount in INR")


class ClaimIntakeRequest(BaseModel):
    claim_id: Optional[str] = None
    policy_id: str = Field(..., description="Policy number, e.g. POL-HLT-2026-8841")
    claimant_name: str = Field(..., description="Full name of policyholder/claimant")
    claimant_email: str = Field(..., description="Contact email for decision notice")
    claim_type: str = Field(..., description="Health | Motor | Home")
    incident_date: str = Field(..., description="ISO date YYYY-MM-DD of hospitalization/incident")
    submission_date: str = Field(default="2026-11-17", description="ISO date YYYY-MM-DD")
    diagnosis_or_incident: str = Field(..., description="Clinical diagnosis or damage summary")
    hospital_or_vendor: str = Field(..., description="Provider / hospital / garage name")
    is_network_provider: bool = Field(default=True)
    raw_narrative: str = Field(..., description="Unstructured narrative, clinical notes, or email text")
    invoice_items: List[InvoiceLineItem] = Field(default_factory=list)
    prior_claims_count_12m: int = Field(default=0, ge=0)
    invoice_hash_duplicate: bool = Field(default=False)


class ClauseCitation(BaseModel):
    clause_id: str
    section_title: str
    rule_type: str
    summary: str
    similarity_score: float
    triggered_impact: str


class LineItemAdjudication(BaseModel):
    item_id: str
    description: str
    category: str
    claimed_amount: float
    deducted_amount: float
    approved_amount: float
    deduction_reason: str
    clause_ref: str


class ActuarialBreakdown(BaseModel):
    gross_claimed_inr: float
    excluded_consumables_inr: float
    sublimit_disallowed_inr: float
    waiting_period_disallowed_inr: float
    eligible_after_clauses_inr: float
    deductible_applied_inr: float
    copay_percentage: float
    copay_amount_inr: float
    sum_insured_cap_inr: float
    net_payable_inr: float
    line_adjudications: List[LineItemAdjudication]


class RiskAssessment(BaseModel):
    risk_score: float = Field(..., ge=0.0, le=10.0, description="0-10 risk score")
    risk_band: str = Field(..., description="LOW (<3.0) | MEDIUM (3.0-7.0) | HIGH (>7.0)")
    fraud_signals: List[str]
    completeness_valid: bool
    missing_documents: List[str]
    requires_siu: bool


class HITLDecisionInput(BaseModel):
    officer_name: str
    officer_role: str = "Senior Claims Adjudicator"
    action: str = Field(..., description="APPROVE | PARTIAL_OVERRIDE | REJECT | ESCALATE_SIU")
    override_payable_inr: Optional[float] = None
    officer_notes: str
    custom_email_body: Optional[str] = None


class NodeTraceEvent(BaseModel):
    node_name: str
    status: str
    model_used: str
    latency_ms: int
    summary: str
    timestamp: str


class ClaimState(TypedDict, total=False):
    claim_id: str
    intake: Dict[str, Any]
    is_valid_claim_inquiry: bool
    triage_category: str
    triage_urgency: str
    extracted_entities: Dict[str, Any]
    policy_record: Dict[str, Any]
    matched_clauses: List[Dict[str, Any]]
    risk_assessment: Dict[str, Any]
    actuarial_breakdown: Dict[str, Any]
    preliminary_outcome: str
    final_outcome: str
    internal_status: str
    requires_hitl: bool
    hitl_reason: str
    hitl_decision: Optional[Dict[str, Any]]
    customer_email_subject: str
    customer_email_body: str
    node_traces: List[Dict[str, Any]]
    audit_hash: str
    groq_mode: str

