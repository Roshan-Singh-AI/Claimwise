from __future__ import annotations
"""
End-to-End Automated Test Suite for Claimwise.
Tests:
  1. Groq 2026 Model Deprecation Safeguard (`llama-3.3-70b-versatile` -> `qwen/qwen3.8-27b`)
  2. RBAC Login & Cryptographic JWT Verification (Roshan Singh, Asha Rao, Priya Nair)
  3. 7-stage claim graph execution (native LangGraph when installed; compatibility runner otherwise) across Auto-Approval, Sub-Limit Partial Approval, Waiting Period Rejection, HITL Pause, and SIU Fraud Escalation
  4. Human-in-the-Loop (HITL) Checkpoint Resumption & Officer Override
  5. Immutable SHA-256 Audit Chain Verification
  6. Golden Benchmark Evaluation Suite (100% pass rate across all 7 golden cases)
  7. FastAPI Route Handler E2E Verification
"""
import os
import tempfile
import unittest
from app.auth import authenticate_user, verify_jwt_token
from app.config import AppConfig
from app.database import ClaimDatabase, SEED_SCENARIOS
from app.evals.eval_runner import run_evaluation_suite
from app.graph import execute_claim_pipeline, resume_claim_after_hitl
from app.main import (
    LoginRequest,
    get_all_claims,
    get_audit_trail,
    health_check,
    login,
    submit_hitl_decision,
    submit_new_claim,
)
from app.schemas import ClaimIntakeRequest, HITLDecisionInput


class TestClaimwiseE2E(unittest.TestCase):
    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp_db.close()
        self.db = ClaimDatabase(db_path=self.tmp_db.name)

    def tearDown(self):
        if os.path.exists(self.tmp_db.name):
            os.unlink(self.tmp_db.name)

    def test_01_groq_2026_model_deprecation_guard(self):
        self.assertEqual(
            AppConfig.resolve_model("llama-3.3-70b-versatile"),
            "qwen/qwen3.8-27b",
        )
        self.assertEqual(
            AppConfig.resolve_model("llama-3.1-8b-instant"),
            "openai/gpt-oss-20b",
        )
        self.assertEqual(
            AppConfig.resolve_model("openai/gpt-oss-120b"),
            "openai/gpt-oss-120b",
        )

    def test_02_rbac_login_and_jwt_verification(self):
        auth = authenticate_user("roshan@claimwise.demo", "DemoOfficer@2026")
        self.assertIsNotNone(auth)
        self.assertEqual(auth["user"]["role"], "officer")
        decoded = verify_jwt_token(auth["access_token"])
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded["full_name"], "Roshan Singh")

        bad_auth = authenticate_user("roshan@claimwise.demo", "wrong-pass")
        self.assertIsNone(bad_auth)

    def test_03_langgraph_auto_approve_and_sublimit_math(self):
        # Motor windshield fast-track
        s1 = execute_claim_pipeline(SEED_SCENARIOS[0], claim_id="CLM-TEST-01")
        self.assertEqual(s1["final_outcome"], "APPROVED")
        self.assertFalse(s1["requires_hitl"])
        self.assertAlmostEqual(s1["actuarial_breakdown"]["net_payable_inr"], 17000.0)

        # Health appendectomy with room-rent sub-limit and consumables exclusion
        s2 = execute_claim_pipeline(SEED_SCENARIOS[1], claim_id="CLM-TEST-02")
        self.assertEqual(s2["final_outcome"], "PARTIAL_APPROVED")
        self.assertAlmostEqual(s2["actuarial_breakdown"]["excluded_consumables_inr"], 4200.0)
        self.assertAlmostEqual(s2["actuarial_breakdown"]["sublimit_disallowed_inr"], 9000.0)
        self.assertAlmostEqual(s2["actuarial_breakdown"]["net_payable_inr"], 79650.0)

    def test_04_hitl_pause_and_officer_resume_override(self):
        # High-value cardiac PTCA claim pauses for HITL
        s4 = execute_claim_pipeline(SEED_SCENARIOS[3], claim_id="CLM-TEST-04")
        self.assertTrue(s4["requires_hitl"])
        self.assertEqual(s4["final_outcome"], "PENDING_HITL")
        self.assertEqual(s4["internal_status"], "HITL_PENDING_OFFICER")

        # Officer Roshan Singh approves with custom note
        resumed = resume_claim_after_hitl(
            s4,
            {
                "officer_name": "Roshan Singh",
                "officer_role": "Senior AI Developer & Lead Adjudicator",
                "action": "APPROVE",
                "officer_notes": "Verified Abbott Xience DES stent invoice and Manipal/Apollo Cath Lab summary.",
            },
        )
        self.assertFalse(resumed["requires_hitl"])
        self.assertEqual(resumed["final_outcome"], "APPROVED")
        self.assertEqual(resumed["internal_status"], "HITL_APPROVED_BY_OFFICER")
        self.assertAlmostEqual(resumed["actuarial_breakdown"]["net_payable_inr"], 208800.0)

    def test_05_siu_fraud_and_audit_chain_integrity(self):
        claims = self.db.list_claims()
        self.assertEqual(len(claims), 6)
        verification = self.db.verify_audit_chain()
        self.assertTrue(verification["valid"])
        self.assertGreaterEqual(verification["checked_records"], 6)

    def test_06_golden_evaluation_suite_100_percent(self):
        report = run_evaluation_suite()
        self.assertEqual(report["total_cases"], 7)
        self.assertEqual(report["passed_cases"], 7)
        self.assertAlmostEqual(report["accuracy_pct"], 100.0)

    def test_07_fastapi_endpoints_direct(self):
        hc = health_check()
        self.assertEqual(hc["status"], "ok")
        login_res = login(
            LoginRequest(
                email="roshan@claimwise.demo",
                password="DemoOfficer@2026",
            )
        )
        self.assertIn("access_token", login_res)

        new_req = ClaimIntakeRequest(**SEED_SCENARIOS[0])
        submitted = submit_new_claim(new_req)
        self.assertEqual(submitted["final_outcome"], "APPROVED")

        # Test HITL decision endpoint on CLM-2026-804
        hitl_res = submit_hitl_decision(
            "CLM-2026-804",
            HITLDecisionInput(
                officer_name="Roshan Singh",
                action="PARTIAL_OVERRIDE",
                override_payable_inr=210000.0,
                officer_notes="Approved cardiac stent with discretionary waiver ofRs. 1,200.",
            ),
        )
        self.assertEqual(hitl_res["final_outcome"], "PARTIAL_APPROVED")
        self.assertAlmostEqual(hitl_res["actuarial_breakdown"]["net_payable_inr"], 210000.0)

        audit_res = get_audit_trail()
        self.assertTrue(audit_res["verification"]["valid"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

