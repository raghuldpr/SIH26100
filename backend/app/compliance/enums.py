"""
Phase 09 — Compliance Rule Engine
enums.py: All enumeration types used across the compliance module.

Design decisions:
- ComplianceStatus contains both external (PASS/FAIL/REVIEW) and internal
  (EXEMPT, NOT_APPLICABLE) states.  The ComplianceResult model exposes an
  `external_status` property that collapses internal states for callers.
- RuleType maps 1-to-1 to evaluator classes registered in the EvaluatorRegistry.
- Operator values are the canonical names used inside RuleDefinition.
- EvidenceSource tracks provenance of each piece of bidder evidence.
"""
import enum


class ComplianceStatus(str, enum.Enum):
    """
    Compliance evaluation outcome.

    External states (returned to API callers):
        PASS   - Requirement is definitively satisfied.
        FAIL   - Requirement is definitively violated.
        REVIEW - Evidence is missing, ambiguous, conflicting, malformed,
                 or insufficient for a deterministic decision.

    Internal states (collapsed before API exposure):
        EXEMPT         - Bidder qualifies for a statutory exemption (MSE/Startup/SC-ST).
                         Maps to PASS externally.
        NOT_APPLICABLE - Rule does not apply to this bidder category or tender type.
                         Maps to PASS externally (requirement is waived).
    """

    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW = "REVIEW"
    EXEMPT = "EXEMPT"
    NOT_APPLICABLE = "NOT_APPLICABLE"

    @property
    def external_status(self) -> "ComplianceStatus":
        """Collapse internal states to the three externally meaningful values."""
        _MAP = {
            ComplianceStatus.EXEMPT: ComplianceStatus.PASS,
            ComplianceStatus.NOT_APPLICABLE: ComplianceStatus.PASS,
        }
        return _MAP.get(self, self)

    @property
    def is_passing(self) -> bool:
        """True when the decision should be treated as a pass by downstream logic."""
        return self.external_status == ComplianceStatus.PASS

    @property
    def is_definitive(self) -> bool:
        """True when the result is not REVIEW — i.e. a hard PASS or FAIL."""
        return self.external_status != ComplianceStatus.REVIEW


class RuleType(str, enum.Enum):
    """
    Evaluator dispatch key.  Each value must have a corresponding evaluator
    class registered in EvaluatorRegistry (evaluator.py).
    """

    NUMERIC = "NUMERIC"
    """Numeric threshold comparison (turnover, net-worth, EMD amount, etc.)."""

    BOOLEAN = "BOOLEAN"
    """Boolean flag check (gst_registered, pan_verified, etc.)."""

    DATE_RANGE = "DATE_RANGE"
    """Date or duration check (validity period, years of experience)."""

    DOCUMENT_PRESENCE = "DOCUMENT_PRESENCE"
    """Checks that a required document has been submitted and is valid."""

    EXPERIENCE = "EXPERIENCE"
    """Similar-work experience checks (project count, contract value, years)."""

    LOGICAL = "LOGICAL"
    """AND / OR / NOT composition of sub-rules."""

    CONDITIONAL = "CONDITIONAL"
    """If-then-else rule chains (e.g. 'if MSE then waive turnover threshold')."""

    EXEMPTION = "EXEMPTION"
    """Statutory exemption rules (MSE, Startup, SC-ST certificate checks)."""


class Operator(str, enum.Enum):
    """
    Comparison operator vocabulary used inside RuleDefinition and operators.py.

    Naming follows the English long-form for clarity in audit logs.
    """

    # Equality
    EQUAL = "EQUAL"
    NOT_EQUAL = "NOT_EQUAL"

    # Ordered comparisons
    GREATER_THAN = "GREATER_THAN"
    GREATER_THAN_OR_EQUAL = "GREATER_THAN_OR_EQUAL"
    LESS_THAN = "LESS_THAN"
    LESS_THAN_OR_EQUAL = "LESS_THAN_OR_EQUAL"

    # Convenience aliases used in requirement normalization
    MINIMUM = "MINIMUM"          # Alias for GREATER_THAN_OR_EQUAL
    MAXIMUM = "MAXIMUM"          # Alias for LESS_THAN_OR_EQUAL

    # Range
    BETWEEN = "BETWEEN"          # Requires required_value = [low, high]

    # Membership
    IN = "IN"                    # Requires required_value = list
    NOT_IN = "NOT_IN"            # Requires required_value = list

    # Document / field existence
    PRESENT = "PRESENT"          # Field / document must exist and be non-null
    ABSENT = "ABSENT"            # Field / document must be absent / null

    # Date comparisons (use DATE_* prefix to avoid confusion with numeric ops)
    DATE_EQUAL = "DATE_EQUAL"                          # actual_date == reference_date
    DATE_BEFORE = "DATE_BEFORE"                        # actual_date < reference_date (exclusive)
    DATE_AFTER = "DATE_AFTER"                          # actual_date > reference_date (exclusive)
    DATE_BEFORE_OR_EQUAL = "DATE_BEFORE_OR_EQUAL"      # actual_date <= reference_date (inclusive)
    DATE_AFTER_OR_EQUAL = "DATE_AFTER_OR_EQUAL"        # actual_date >= reference_date (inclusive)
    DATE_BETWEEN = "DATE_BETWEEN"                      # start_date <= actual_date <= end_date


class EvidenceSource(str, enum.Enum):
    """Provenance of a BidderEvidence value."""

    UPLOADED_DOCUMENT = "UPLOADED_DOCUMENT"
    """Extracted from an OCR-processed document uploaded by the bidder."""

    MANUAL_ENTRY = "MANUAL_ENTRY"
    """Entered directly by the bidder via the platform UI."""

    API_VERIFIED = "API_VERIFIED"
    """Retrieved and confirmed from a government API (e.g. GST portal, MCA21)."""

    SYSTEM_DERIVED = "SYSTEM_DERIVED"
    """Computed internally by the platform from other verified evidence."""
