"""
Phase 09 — Compliance Rule Engine
Public API surface for app.compliance.

Importing from `app.compliance` directly gives access to the most commonly
needed symbols without needing to know internal module layout.
"""
from app.compliance.boolean import BooleanEvaluator
from app.compliance.conditional import ConditionalEvaluator
from app.compliance.dates import DateEvaluator
from app.compliance.documents import DocumentEvaluator
from app.compliance.engine import ComplianceEngine, engine
from app.compliance.enums import (
    ComplianceStatus,
    EvidenceSource,
    Operator,
    RuleType,
)
from app.compliance.evaluator import BaseEvaluator, EvaluatorRegistry
from app.compliance.experience import ExperienceEvaluator
from app.compliance.exemptions import ExemptionEvaluator
from app.compliance.logical import LogicalEvaluator
from app.compliance.models import (
    BidderEvidence,
    ComplianceResult,
    Requirement,
    RuleDefinition,
)
from app.compliance.numeric import NumericEvaluator

__all__ = [
    # Engine
    "ComplianceEngine",
    "engine",
    # Base
    "BaseEvaluator",
    "EvaluatorRegistry",
    # Evaluators
    "NumericEvaluator",
    "BooleanEvaluator",
    "DateEvaluator",
    "DocumentEvaluator",
    "ExperienceEvaluator",
    "ExemptionEvaluator",
    "LogicalEvaluator",
    "ConditionalEvaluator",
    # Models
    "Requirement",
    "BidderEvidence",
    "RuleDefinition",
    "ComplianceResult",
    # Enums
    "ComplianceStatus",
    "RuleType",
    "Operator",
    "EvidenceSource",
]
