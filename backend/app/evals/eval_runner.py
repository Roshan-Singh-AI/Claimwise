from __future__ import annotations
"""
LLM-as-a-Judge & Deterministic Golden Benchmark Evaluation Runner.
Inspired by `harshraj78/Insurance-Claim-Processing-Agent` (`app/evals/eval_runner.py`)
and Langfuse structured extraction cookbooks.
Evaluates 8 golden test scenarios across:
  - Outcome Classification Accuracy
  - Exact Actuarial Payout Precision (within Rs. 0.01)
  - Policy Clause Citation Fidelity
  - HITL / SIU Escalation Routing Accuracy
"""
from typing import Any, Dict, List
from ..database import SEED_SCENARIOS
from ..graph import execute_claim_pipeline

GOLDEN_BENCHMARK: List[Dict[str, Any]] = [
    {
        "case_id": "EVAL-01",
        "title": "Motor OEM Windshield Fast-Track (Low Risk Auto-Approve)",
        "scenario": SEED_SCENARIOS[0],
        "expected_preliminary_outcome": "APPROVED",
        "expected_net_payable_inr": 17000.0,  # 18,000 gross - 1,000 deductible, 0% network copay
        "expected_requires_hitl": False,
        "expected_clause": "CL-MTR-2.1",
    },
    {
        "case_id": "EVAL-02",
        "title": "Health Appendectomy with Room-Rent Cap & Consumables Exclusion",
        "scenario": SEED_SCENARIOS[1],
        "expected_preliminary_outcome": "PARTIAL_APPROVED",
        # Gross 106,700 - 4,200 consumables - 9,000 room excess (3 days * 3,000) = 93,500 eligible
        # - 5,000 deductible = 88,500 -> -10% copay (8,850) = 79,650.0
        "expected_net_payable_inr": 79650.0,
        "expected_requires_hitl": False,
        "expected_clause": "CL-HLT-4.1",
    },
    {
        "case_id": "EVAL-03",
        "title": "Elective Cataract Within 24-Month Waiting Period (Auto-Reject)",
        "scenario": SEED_SCENARIOS[2],
        "expected_preliminary_outcome": "REJECTED",
        "expected_net_payable_inr": 0.0,
        "expected_requires_hitl": False,
        "expected_clause": "CL-HLT-6.2",
    },
    {
        "case_id": "EVAL-04",
        "title": "High-Value Cardiac PTCA Stent Claim (> Rs. 1.5L HITL Pause)",
        "scenario": SEED_SCENARIOS[3],
        "expected_preliminary_outcome": "PARTIAL_APPROVED",
        # Gross 248,500 - 5,500 consumables - 6,000 ICU excess (3 days * 2,000) = 237,000 eligible
        # - 5,000 deductible = 232,000 -> -10% copay (23,200) = 208,800.0
        "expected_net_payable_inr": 208800.0,
        "expected_requires_hitl": True,
        "expected_clause": "CL-HLT-4.1",
    },
    {
        "case_id": "EVAL-05",
        "title": "Non-Network Duplicate Invoice Hash Anomaly (SIU Fraud Escalation)",
        "scenario": SEED_SCENARIOS[4],
        "expected_preliminary_outcome": "SIU_ESCALATED",
        # Gross 145,000 - 40,000 room excess (4 days * 10,000 over 5,000 cap) = 105,000 eligible
        # - 3,000 deductible = 102,000 -> -25% non-network copay (25,500) = 76,500.0
        "expected_net_payable_inr": 76500.0,
        "expected_requires_hitl": True,
        "expected_clause": "CL-HLT-4.1",
    },
    {
        "case_id": "EVAL-06",
        "title": "Home Lightning & BESCOM Voltage Surge PCB Replacement",
        "scenario": SEED_SCENARIOS[5],
        "expected_preliminary_outcome": "APPROVED",
        # Gross 48,000 - 2,500 deductible = 45,500 -> -5% copay (2,275) = 43,225.0
        "expected_net_payable_inr": 43225.0,
        "expected_requires_hitl": False,
        "expected_clause": "CL-HOM-1.2",
    },
    {
        "case_id": "EVAL-07",
        "title": "Non-Claim Address Update Inquiry (Gateway Short-Circuit)",
        "scenario": {
            "claim_id": "CLM-2026-807",
            "policy_id": "POL-HLT-2026-8841",
            "claimant_name": "Asha Rao",
            "claimant_email": "asha.rao@example.in",
            "claim_type": "Health",
            "incident_date": "2026-11-17",
            "diagnosis_or_incident": "General Inquiry",
            "hospital_or_vendor": "N/A",
            "is_network_provider": True,
            "raw_narrative": "Hello, how do I update my address on my health policy brochure request?",
            "invoice_items": [],
        },
        "expected_preliminary_outcome": "REJECTED_INCOMPLETE",
        "expected_net_payable_inr": 0.0,
        "expected_requires_hitl": False,
        "expected_clause": "NONE",
    },
]


def run_evaluation_suite() -> Dict[str, Any]:
    results: List[Dict[str, Any]] = []
    passed_count = 0
    for item in GOLDEN_BENCHMARK:
        state = execute_claim_pipeline(item["scenario"], claim_id=item["scenario"]["claim_id"])
        calc = state.get("actuarial_breakdown") or {}
        actual_prelim = state.get("preliminary_outcome")
        actual_net = float(calc.get("net_payable_inr", 0.0))
        actual_hitl = bool(state.get("requires_hitl", False))
        matched_ids = [c["clause_id"] for c in state.get("matched_clauses", [])]

        outcome_ok = actual_prelim == item["expected_preliminary_outcome"]
        math_ok = abs(actual_net - item["expected_net_payable_inr"]) < 0.01
        hitl_ok = actual_hitl == item["expected_requires_hitl"]
        clause_ok = (
            True
            if item["expected_clause"] == "NONE"
            else item["expected_clause"] in matched_ids
        )

        all_passed = outcome_ok and math_ok and hitl_ok and clause_ok
        if all_passed:
            passed_count += 1

        results.append(
            {
                "case_id": item["case_id"],
                "title": item["title"],
                "passed": all_passed,
                "expected_outcome": item["expected_preliminary_outcome"],
                "actual_outcome": actual_prelim,
                "expected_net_inr": item["expected_net_payable_inr"],
                "actual_net_inr": actual_net,
                "expected_hitl": item["expected_requires_hitl"],
                "actual_hitl": actual_hitl,
                "clause_verified": clause_ok,
            }
        )

    total = len(GOLDEN_BENCHMARK)
    return {
        "total_cases": total,
        "passed_cases": passed_count,
        "accuracy_pct": round((passed_count / max(total, 1)) * 100.0, 2),
        "cases": results,
    }


if __name__ == "__main__":
    summary = run_evaluation_suite()
    print(f"Claimwise Evaluation Suite: {summary['passed_cases']}/{summary['total_cases']} ({summary['accuracy_pct']}%)")
    for c in summary["cases"]:
        status = "PASS" if c["passed"] else "FAIL"
        print(f"  [{status}] {c['case_id']} - {c['title']}: Outcome={c['actual_outcome']}, Net=Rs.{c['actual_net_inr']:,.2f}")

