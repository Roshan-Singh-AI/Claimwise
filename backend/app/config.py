from __future__ import annotations
"""
Configuration & Groq 2026 Model Safeguards.
Automatically upgrades deprecated Groq models (llama-3.3-70b-versatile, llama-3.1-8b-instant,
qwen/qwen3-32b) deprecated in Aug/Sep 2026 to active 2026 LPU models.
References:
- Groq Deprecations: https://console.groq.com/docs/deprecations
- Groq Supported Models: https://console.groq.com/docs/models
"""
import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
from dataclasses import dataclass, field
from typing import Dict

DEPRECATED_GROQ_MODEL_MAP: Dict[str, str] = {
    "llama-3.3-70b-versatile": "qwen/qwen3.8-27b",
    "llama-3.1-8b-instant": "openai/gpt-oss-20b",
    "qwen/qwen3-32b": "qwen/qwen3.8-27b",
    "qwen/qwen3.6-27b": "qwen/qwen3.8-27b",
    "deepseek-r1-distill-llama-70b": "openai/gpt-oss-120b",
}

SUPPORTED_2026_MODELS = {
    "qwen/qwen3.8-27b": {
        "name": "Qwen 3.8 27B (Groq LPU)",
        "speed_tok_s": 450,
        "input_cost_per_1m": 0.80,
        "output_cost_per_1m": 4.00,
        "role": "Primary Structured Extraction & Policy RAG Reasoning",
    },
    "openai/gpt-oss-120b": {
        "name": "OpenAI GPT-OSS 120B (Groq LPU)",
        "speed_tok_s": 310,
        "input_cost_per_1m": 0.75,
        "output_cost_per_1m": 3.00,
        "role": "Complex Multi-Hop Adjudication & Appeal Synthesis",
    },
    "openai/gpt-oss-20b": {
        "name": "OpenAI GPT-OSS 20B (Groq LPU)",
        "speed_tok_s": 620,
        "input_cost_per_1m": 0.15,
        "output_cost_per_1m": 0.60,
        "role": "High-Speed Gateway Triage & Completeness Classification",
    },
}


@dataclass
class AppConfig:
    groq_api_key: str = field(default_factory=lambda: os.getenv("GROQ_API_KEY", ""))
    primary_model: str = field(
        default_factory=lambda: os.getenv("CLAIMFORGE_PRIMARY_MODEL", "qwen/qwen3.8-27b")
    )
    reasoning_model: str = field(
        default_factory=lambda: os.getenv("CLAIMFORGE_REASONING_MODEL", "openai/gpt-oss-120b")
    )
    triage_model: str = field(
        default_factory=lambda: os.getenv("CLAIMFORGE_TRIAGE_MODEL", "openai/gpt-oss-20b")
    )
    jwt_secret: str = field(
        default_factory=lambda: os.getenv(
            "CLAIMFORGE_JWT_SECRET", "claimwise-dev-only-secret-change-before-deployment"
        )
    )
    db_path: str = field(
        default_factory=lambda: os.getenv("CLAIMFORGE_DB_PATH", "./data/claimwise.sqlite")
    )
    hitl_threshold_inr: float = field(
        default_factory=lambda: float(os.getenv("CLAIMFORGE_HITL_THRESHOLD_INR", "150000"))
    )

    def __post_init__(self):
        self.primary_model = self.resolve_model(self.primary_model)
        self.reasoning_model = self.resolve_model(self.reasoning_model)
        self.triage_model = self.resolve_model(self.triage_model)

    @staticmethod
    def resolve_model(model_name: str) -> str:
        cleaned = (model_name or "").strip()
        if cleaned in DEPRECATED_GROQ_MODEL_MAP:
            return DEPRECATED_GROQ_MODEL_MAP[cleaned]
        return cleaned or "qwen/qwen3.8-27b"


settings = AppConfig()

