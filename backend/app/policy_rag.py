from __future__ import annotations
"""
Policy Knowledge Base & Hybrid Semantic + Metadata RAG Retriever.
Models IRDAI-compliant Health, Motor, and Home insurance policies with
waiting periods, room-rent caps, consumable exclusions, and co-payments.
"""
import math
import re
from typing import Any, Dict, List, Optional

MASTER_POLICIES: Dict[str, Dict[str, Any]] = {
    "POL-HLT-2026-8841": {
        "policy_id": "POL-HLT-2026-8841",
        "holder_name": "Asha Rao",
        "holder_email": "asha.rao@example.in",
        "line": "Health",
        "plan_name": "Optima Care Platinum Shield",
        "inception_date": "2024-03-10",
        "expiry_date": "2027-03-09",
        "sum_insured_inr": 1000000.0,
        "remaining_balance_inr": 850000.0,
        "deductible_inr": 5000.0,
        "network_copay_pct": 10.0,
        "non_network_copay_pct": 20.0,
        "room_rent_daily_cap_inr": 8000.0,
        "icu_daily_cap_inr": 16000.0,
        "specific_waiting_period_months": 24,
        "specific_waiting_diseases": [
            "cataract",
            "hernia",
            "joint replacement",
            "kidney stone",
            "sinusitis",
            "cholecystectomy",
        ],
        "clauses": [
            {
                "clause_id": "CL-HLT-4.1",
                "section_title": "Section 4.1 — Room Rent & Boarding Sub-Limit",
                "rule_type": "SUB_LIMIT",
                "keywords": ["room", "rent", "boarding", "ward", "suite", "daily", "icu"],
                "summary": "Room & boarding charges are capped at 1% of Sum Insured (Rs. 8,000/day) for normal rooms and Rs. 16,000/day for ICU.",
            },
            {
                "clause_id": "CL-HLT-5.3",
                "section_title": "Section 5.3 — Non-Payable Consumables (IRDAI Annexure-I)",
                "rule_type": "EXCLUSION",
                "keywords": ["consumables", "gloves", "ppe", "masks", "syringes", "cotton", "sanitary", "kit"],
                "summary": "Non-medical consumables (PPE kits, surgical gloves, syringes, hygiene kits) listed under IRDAI Annexure-I are 100% excluded.",
            },
            {
                "clause_id": "CL-HLT-6.2",
                "section_title": "Section 6.2 — 24-Month Specific Illness Waiting Period",
                "rule_type": "WAITING_PERIOD",
                "keywords": ["waiting", "period", "cataract", "hernia", "joint", "replacement", "stone", "24 months"],
                "summary": "Specified elective procedures (Cataract, Hernia, Joint Replacement, Kidney Stones) carry a mandatory 24-month waiting period from policy inception.",
            },
            {
                "clause_id": "CL-HLT-7.4",
                "section_title": "Section 7.4 — Mandatory Co-Payment & Standard Deductible",
                "rule_type": "COPAY_DEDUCTIBLE",
                "keywords": ["copay", "co-payment", "deductible", "network", "reimbursement"],
                "summary": "A per-claim deductible of Rs. 5,000 applies, followed by 10% co-pay at network hospitals (20% at non-network hospitals).",
            },
        ],
    },
    "POL-HLT-2026-9920": {
        "policy_id": "POL-HLT-2026-9920",
        "holder_name": "Vikram Mehta",
        "holder_email": "vikram.mehta@example.in",
        "line": "Health",
        "plan_name": "Arogya Essential Gold",
        "inception_date": "2026-02-01",
        "expiry_date": "2027-01-31",
        "sum_insured_inr": 500000.0,
        "remaining_balance_inr": 500000.0,
        "deductible_inr": 3000.0,
        "network_copay_pct": 10.0,
        "non_network_copay_pct": 25.0,
        "room_rent_daily_cap_inr": 5000.0,
        "icu_daily_cap_inr": 10000.0,
        "specific_waiting_period_months": 24,
        "specific_waiting_diseases": [
            "cataract",
            "hernia",
            "joint replacement",
            "kidney stone",
        ],
        "clauses": [
            {
                "clause_id": "CL-HLT-6.2",
                "section_title": "Section 6.2 — 24-Month Specific Illness Waiting Period",
                "rule_type": "WAITING_PERIOD",
                "keywords": ["waiting", "period", "cataract", "hernia", "joint", "stone", "months"],
                "summary": "Elective procedures including Bilateral Cataract and Inguinal Hernia are excluded during the first 24 months from policy inception (2026-02-01).",
            },
            {
                "clause_id": "CL-HLT-4.1",
                "section_title": "Section 4.1 — Room Rent Daily Cap",
                "rule_type": "SUB_LIMIT",
                "keywords": ["room", "rent", "icu", "daily"],
                "summary": "Standard room rent capped at Rs. 5,000/day; ICU capped at Rs. 10,000/day.",
            },
        ],
    },
    "POL-MTR-2026-3092": {
        "policy_id": "POL-MTR-2026-3092",
        "holder_name": "Asha Rao",
        "holder_email": "asha.rao@example.in",
        "line": "Motor",
        "plan_name": "Zero-Dep Comprehensive Motor Protect",
        "inception_date": "2025-06-15",
        "expiry_date": "2026-12-31",
        "sum_insured_inr": 650000.0,
        "remaining_balance_inr": 650000.0,
        "deductible_inr": 1000.0,
        "network_copay_pct": 0.0,
        "non_network_copay_pct": 10.0,
        "room_rent_daily_cap_inr": 0.0,
        "icu_daily_cap_inr": 0.0,
        "specific_waiting_period_months": 0,
        "specific_waiting_diseases": [],
        "clauses": [
            {
                "clause_id": "CL-MTR-2.1",
                "section_title": "Section 2.1 — OEM Glass & Windshield Replacement Fast-Track",
                "rule_type": "COVERAGE",
                "keywords": ["windshield", "glass", "oem", "crack", "motor", "labor"],
                "summary": "OEM front/rear windshield replacement at authorized network garages is covered at 100% with zero depreciation, subject only to Rs. 1,000 compulsory deductible.",
            },
            {
                "clause_id": "CL-MTR-3.4",
                "section_title": "Section 3.4 — Consumables & Lubricants Exclusion",
                "rule_type": "EXCLUSION",
                "keywords": ["consumables", "oil", "coolant", "nuts", "bolts", "washers"],
                "summary": "Engine oil, coolant top-ups, and sundry fasteners are excluded unless covered by a Consumables Add-On.",
            },
        ],
    },
    "POL-HOM-2026-5510": {
        "policy_id": "POL-HOM-2026-5510",
        "holder_name": "Kiran Deshmukh",
        "holder_email": "kiran.deshmukh@example.in",
        "line": "Home",
        "plan_name": "Griha Raksha Comprehensive Home & Appliance Cover",
        "inception_date": "2025-01-10",
        "expiry_date": "2027-01-09",
        "sum_insured_inr": 400000.0,
        "remaining_balance_inr": 380000.0,
        "deductible_inr": 2500.0,
        "network_copay_pct": 5.0,
        "non_network_copay_pct": 10.0,
        "room_rent_daily_cap_inr": 0.0,
        "icu_daily_cap_inr": 0.0,
        "specific_waiting_period_months": 0,
        "specific_waiting_diseases": [],
        "clauses": [
            {
                "clause_id": "CL-HOM-1.2",
                "section_title": "Section 1.2 — Lightning & Grid Surge Appliance Protection",
                "rule_type": "COVERAGE",
                "keywords": ["lightning", "surge", "voltage", "appliance", "inverter", "pcb"],
                "summary": "Direct lightning strike and BESCOM/utility voltage surge damage to domestic electronics is covered up to Rs. 4,00,000 with Rs. 2,500 deductible and 5% co-pay.",
            },
        ],
    },
}


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def get_policy(policy_id: str) -> Optional[Dict[str, Any]]:
    return MASTER_POLICIES.get((policy_id or "").strip().upper())


def retrieve_relevant_clauses(
    policy_id: str, query_text: str, invoice_categories: List[str]
) -> List[Dict[str, Any]]:
    policy = get_policy(policy_id)
    if not policy:
        return []
    q_tokens = set(_tokenize(query_text) + [c.lower() for c in invoice_categories])
    results: List[Dict[str, Any]] = []
    for clause in policy.get("clauses", []):
        kw_set = set(_tokenize(" ".join(clause["keywords"]) + " " + clause["summary"]))
        overlap = len(q_tokens.intersection(kw_set))
        denom = math.sqrt(max(len(q_tokens), 1) * max(len(kw_set), 1))
        raw_sim = overlap / denom if denom else 0.0
        # Boost baseline relevance for mandatory policy rules
        score = round(min(0.99, 0.68 + raw_sim * 0.45), 3)
        results.append(
            {
                "clause_id": clause["clause_id"],
                "section_title": clause["section_title"],
                "rule_type": clause["rule_type"],
                "summary": clause["summary"],
                "similarity_score": score,
            }
        )
    results.sort(key=lambda x: x["similarity_score"], reverse=True)
    return results

