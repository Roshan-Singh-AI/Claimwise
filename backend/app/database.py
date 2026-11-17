from __future__ import annotations
"""
SQLite State & Immutable SHA-256 Hash-Chained Audit Trail Persistence Layer.
Also seeds 6 realistic end-to-end showcase claims across Health, Motor, and Home lines.
"""
import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from .config import settings
from .graph import execute_claim_pipeline

SEED_SCENARIOS: List[Dict[str, Any]] = [
    {
        "claim_id": "CLM-2026-801",
        "policy_id": "POL-MTR-2026-3092",
        "claimant_name": "Asha Rao",
        "claimant_email": "asha.rao@example.in",
        "claim_type": "Motor",
        "incident_date": "2026-11-10",
        "submission_date": "2026-11-11",
        "diagnosis_or_incident": "Front laminated windshield shattered by highway gravel impact on NH-48",
        "hospital_or_vendor": "Bosch Car Service Authorized Glass Hub, Bengaluru",
        "is_network_provider": True,
        "raw_narrative": "Driving on NH-48 near Electronic City when a gravel stone cracked the front OEM windshield. Replaced at authorized garage.",
        "prior_claims_count_12m": 0,
        "invoice_hash_duplicate": False,
        "invoice_items": [
            {
                "item_id": "ITEM-M1",
                "description": "OEM Acoustic Laminated Front Windshield Glass",
                "category": "parts",
                "code": "OEM-WS-7721",
                "quantity": 1,
                "days": 1,
                "claimed_amount": 14500.0,
            },
            {
                "item_id": "ITEM-M2",
                "description": "Polyurethane Sealant & Calibration Labor",
                "category": "labor",
                "code": "LAB-GLS-02",
                "quantity": 1,
                "days": 1,
                "claimed_amount": 3500.0,
            },
        ],
    },
    {
        "claim_id": "CLM-2026-802",
        "policy_id": "POL-HLT-2026-8841",
        "claimant_name": "Asha Rao",
        "claimant_email": "asha.rao@example.in",
        "claim_type": "Health",
        "incident_date": "2026-11-04",
        "submission_date": "2026-11-08",
        "diagnosis_or_incident": "Acute Laparoscopic Appendectomy (ICD-10 K35.80)",
        "hospital_or_vendor": "Manipal Hospital, Old Airport Road, Bengaluru",
        "is_network_provider": True,
        "raw_narrative": "Admitted for emergency laparoscopic appendectomy for 3 days in private deluxe room. Discharged in stable condition.",
        "prior_claims_count_12m": 1,
        "invoice_hash_duplicate": False,
        "invoice_items": [
            {
                "item_id": "ITEM-H1",
                "description": "Private Deluxe Room Boarding (3 Days @ Rs. 11,000/day)",
                "category": "room_rent",
                "code": "RM-DLX-03",
                "quantity": 1,
                "days": 3,
                "claimed_amount": 33000.0,
            },
            {
                "item_id": "ITEM-H2",
                "description": "Laparoscopic Appendectomy Surgical Package & OT Charges",
                "category": "surgery",
                "code": "CPT-44970",
                "quantity": 1,
                "days": 1,
                "claimed_amount": 58000.0,
            },
            {
                "item_id": "ITEM-H3",
                "description": "In-Patient Pharmacy & IV Antibiotics",
                "category": "pharmacy",
                "code": "PHM-ANT-11",
                "quantity": 1,
                "days": 1,
                "claimed_amount": 11500.0,
            },
            {
                "item_id": "ITEM-H4",
                "description": "PPE Kits, Nitrile Gloves, Syringes & Hygiene Consumables",
                "category": "consumables",
                "code": "IRD-EXCL-01",
                "quantity": 1,
                "days": 1,
                "claimed_amount": 4200.0,
            },
        ],
    },
    {
        "claim_id": "CLM-2026-803",
        "policy_id": "POL-HLT-2026-9920",
        "claimant_name": "Vikram Mehta",
        "claimant_email": "vikram.mehta@example.in",
        "claim_type": "Health",
        "incident_date": "2026-11-12",
        "submission_date": "2026-11-14",
        "diagnosis_or_incident": "Elective Bilateral Cataract Phacoemulsification with IOL (ICD-10 H25.1)",
        "hospital_or_vendor": "Narayana Nethralaya, Indiranagar, Bengaluru",
        "is_network_provider": True,
        "raw_narrative": "Elective cataract surgery with multifocal lens implantation performed 9 months after policy inception (2026-02-01).",
        "prior_claims_count_12m": 0,
        "invoice_hash_duplicate": False,
        "invoice_items": [
            {
                "item_id": "ITEM-C1",
                "description": "Phacoemulsification Cataract Procedure & Foldable IOL Package",
                "category": "surgery",
                "code": "CPT-66984",
                "quantity": 1,
                "days": 1,
                "claimed_amount": 46000.0,
            },
        ],
    },
    {
        "claim_id": "CLM-2026-804",
        "policy_id": "POL-HLT-2026-8841",
        "claimant_name": "Asha Rao",
        "claimant_email": "asha.rao@example.in",
        "claim_type": "Health",
        "incident_date": "2026-11-14",
        "submission_date": "2026-11-16",
        "diagnosis_or_incident": "Acute Coronary Syndrome — Percutaneous Coronary Angioplasty (PTCA with Drug-Eluting Stent, ICD-10 I21.9)",
        "hospital_or_vendor": "Apollo Hospitals, Bannerghatta Road, Bengaluru",
        "is_network_provider": True,
        "raw_narrative": "Emergency cardiac admission in ICU for 3 days followed by 2 days in standard ward. Coronary angiography and single DES stent deployment performed.",
        "prior_claims_count_12m": 1,
        "invoice_hash_duplicate": False,
        "invoice_items": [
            {
                "item_id": "ITEM-K1",
                "description": "Cardiac ICU Boarding & Monitoring (3 Days @ Rs. 18,000/day)",
                "category": "icu",
                "code": "ICU-CRD-03",
                "quantity": 1,
                "days": 3,
                "claimed_amount": 54000.0,
            },
            {
                "item_id": "ITEM-K2",
                "description": "Cath Lab PTCA Procedure & Abbott Xience Drug-Eluting Stent",
                "category": "surgery",
                "code": "CPT-92928",
                "quantity": 1,
                "days": 1,
                "claimed_amount": 165000.0,
            },
            {
                "item_id": "ITEM-K3",
                "description": "Cardiac Biomarkers, Echo & Post-Op Pharmacy",
                "category": "diagnostics",
                "code": "DG-CRD-09",
                "quantity": 1,
                "days": 1,
                "claimed_amount": 24000.0,
            },
            {
                "item_id": "ITEM-K4",
                "description": "Disposable Cath Gown, Gloves & Non-Medical Kit",
                "category": "consumables",
                "code": "IRD-EXCL-09",
                "quantity": 1,
                "days": 1,
                "claimed_amount": 5500.0,
            },
        ],
    },
    {
        "claim_id": "CLM-2026-805",
        "policy_id": "POL-HLT-2026-9920",
        "claimant_name": "Vikram Mehta",
        "claimant_email": "vikram.mehta@example.in",
        "claim_type": "Health",
        "incident_date": "2026-11-15",
        "submission_date": "2026-11-16",
        "diagnosis_or_incident": "Acute Viral Gastroenteritis & Dehydration Management (ICD-10 A08.4)",
        "hospital_or_vendor": "Unverified Sunrise Nursing Home (Non-Network)",
        "is_network_provider": False,
        "raw_narrative": "Submitted high-value reimbursement claim from non-network clinic with duplicate invoice SHA-256 hash and 4 prior claims in 12 months.",
        "prior_claims_count_12m": 4,
        "invoice_hash_duplicate": True,
        "invoice_items": [
            {
                "item_id": "ITEM-F1",
                "description": "Suite Room Charges (4 Days @ Rs. 15,000/day)",
                "category": "room_rent",
                "code": "RM-STE-04",
                "quantity": 1,
                "days": 4,
                "claimed_amount": 60000.0,
            },
            {
                "item_id": "ITEM-F2",
                "description": "In-Patient IV Infusions & Broad Panel Diagnostics",
                "category": "diagnostics",
                "code": "DG-GEN-99",
                "quantity": 1,
                "days": 1,
                "claimed_amount": 85000.0,
            },
        ],
    },
    {
        "claim_id": "CLM-2026-806",
        "policy_id": "POL-HOM-2026-5510",
        "claimant_name": "Kiran Deshmukh",
        "claimant_email": "kiran.deshmukh@example.in",
        "claim_type": "Home",
        "incident_date": "2026-11-09",
        "submission_date": "2026-11-10",
        "diagnosis_or_incident": "Lightning & BESCOM High-Voltage Surge Damage to Home Inverter & OLED TV PCB",
        "hospital_or_vendor": "LG & Luminous Authorized Service Center, Whitefield",
        "is_network_provider": True,
        "raw_narrative": "Severe thunderstorm caused a grid voltage surge that burned out the main PCB of our 65-inch OLED TV and sine-wave home inverter.",
        "prior_claims_count_12m": 0,
        "invoice_hash_duplicate": False,
        "invoice_items": [
            {
                "item_id": "ITEM-P1",
                "description": "65-inch OLED Main Logic Board & Power Supply Module Replacement",
                "category": "surge_damage",
                "code": "LG-PCB-65C",
                "quantity": 1,
                "days": 1,
                "claimed_amount": 38500.0,
            },
            {
                "item_id": "ITEM-P2",
                "description": "Luminous 1500VA Pure Sine Wave Inverter MOSFET Board Repair",
                "category": "surge_damage",
                "code": "LUM-INV-15",
                "quantity": 1,
                "days": 1,
                "claimed_amount": 9500.0,
            },
        ],
    },
]


class ClaimDatabase:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or settings.db_path
        self._init_schema()
        self._seed_if_empty()

    @contextmanager
    def _conn(self):
        parent = os.path.dirname(os.path.abspath(self.db_path))
        os.makedirs(parent, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self):
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS claims (
                    claim_id TEXT PRIMARY KEY,
                    policy_id TEXT NOT NULL,
                    claimant_name TEXT NOT NULL,
                    claim_type TEXT NOT NULL,
                    final_outcome TEXT NOT NULL,
                    internal_status TEXT NOT NULL,
                    gross_claimed_inr REAL NOT NULL,
                    net_payable_inr REAL NOT NULL,
                    risk_score REAL NOT NULL,
                    requires_hitl INTEGER NOT NULL,
                    state_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_chain (
                    seq_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    claim_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    prev_hash TEXT NOT NULL,
                    record_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def append_audit_event(
        self, claim_id: str, event_type: str, actor: str, summary: str
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self._conn() as conn:
            row = conn.execute(
                "SELECT record_hash FROM audit_chain ORDER BY seq_id DESC LIMIT 1"
            ).fetchone()
            prev_hash = row["record_hash"] if row else "0" * 64
            raw = f"{prev_hash}|{claim_id}|{event_type}|{actor}|{summary}|{now}"
            rec_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
            conn.execute(
                """
                INSERT INTO audit_chain (claim_id, event_type, actor, summary, prev_hash, record_hash, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (claim_id, event_type, actor, summary, prev_hash, rec_hash, now),
            )
            conn.commit()
        return {
            "claim_id": claim_id,
            "event_type": event_type,
            "actor": actor,
            "summary": summary,
            "prev_hash": prev_hash,
            "record_hash": rec_hash,
            "created_at": now,
        }

    def verify_audit_chain(self) -> Dict[str, Any]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM audit_chain ORDER BY seq_id ASC").fetchall()
        expected_prev = "0" * 64
        for r in rows:
            raw = f"{r['prev_hash']}|{r['claim_id']}|{r['event_type']}|{r['actor']}|{r['summary']}|{r['created_at']}"
            recomputed = hashlib.sha256(raw.encode("utf-8")).hexdigest()
            if r["prev_hash"] != expected_prev or recomputed != r["record_hash"]:
                return {"valid": False, "checked_records": len(rows), "broken_seq_id": r["seq_id"]}
            expected_prev = r["record_hash"]
        return {
            "valid": True,
            "checked_records": len(rows),
            "head_hash": expected_prev,
        }

    def save_claim_state(self, state: Dict[str, Any], actor: str = "LangGraph Orchestrator"):
        cid = state["claim_id"]
        intake = state["intake"]
        calc = state.get("actuarial_breakdown") or {}
        risk = state.get("risk_assessment") or {}
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO claims (
                    claim_id, policy_id, claimant_name, claim_type,
                    final_outcome, internal_status, gross_claimed_inr,
                    net_payable_inr, risk_score, requires_hitl, state_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cid,
                    intake.get("policy_id", ""),
                    intake.get("claimant_name", ""),
                    intake.get("claim_type", "Health"),
                    state.get("final_outcome", "PENDING"),
                    state.get("internal_status", "PROCESSING"),
                    float(calc.get("gross_claimed_inr", 0.0)),
                    float(calc.get("net_payable_inr", 0.0)),
                    float(risk.get("risk_score", 0.0)),
                    1 if state.get("requires_hitl") else 0,
                    json.dumps(state),
                    now,
                ),
            )
            conn.commit()
        self.append_audit_event(
            claim_id=cid,
            event_type=state.get("internal_status", "UPDATED"),
            actor=actor,
            summary=(
                f"Outcome={state.get('final_outcome')} | "
                f"Gross=Rs.{calc.get('gross_claimed_inr', 0.0):,.2f} | "
                f"Net=Rs.{calc.get('net_payable_inr', 0.0):,.2f}"
            ),
        )

    def _seed_if_empty(self):
        with self._conn() as conn:
            cnt = conn.execute("SELECT COUNT(*) AS c FROM claims").fetchone()["c"]
        if cnt == 0:
            for scenario in SEED_SCENARIOS:
                state = execute_claim_pipeline(scenario, claim_id=scenario["claim_id"])
                self.save_claim_state(state, actor="LangGraph Seed Pipeline")

    def list_claims(self) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT state_json FROM claims ORDER BY claim_id ASC"
            ).fetchall()
        return [json.loads(r["state_json"]) for r in rows]

    def get_claim(self, claim_id: str) -> Optional[Dict[str, Any]]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT state_json FROM claims WHERE claim_id = ?", (claim_id,)
            ).fetchone()
        return json.loads(row["state_json"]) if row else None

    def list_audit_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM audit_chain ORDER BY seq_id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

