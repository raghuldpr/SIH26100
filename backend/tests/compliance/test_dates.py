"""
Phase 09 — Compliance Rule Engine
tests/compliance/test_dates.py: Comprehensive DateEvaluator tests.

Test matrix
-----------
Operators : DATE_EQUAL, DATE_BEFORE, DATE_AFTER,
            DATE_BEFORE_OR_EQUAL, DATE_AFTER_OR_EQUAL, DATE_BETWEEN
Evidence  : datetime.date, datetime.datetime (naive + aware),
            ISO 8601 strings, alternative string formats,
            None evidence, None value, invalid strings, non-date types
Boundaries: exact equality, one-day before/after boundary
Ranges    : in range, on each bound, one day outside each side
Edge cases: start == end range, misconfigured bounds, low confidence,
            invalid operators, missing required_value, date ≡ datetime
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone, timedelta

import pytest

from app.compliance.dates import DateEvaluator
from app.compliance.enums import ComplianceStatus, Operator, RuleType
from app.compliance.models import Requirement, RuleDefinition
from app.models.enums import RequirementType

from tests.compliance.conftest import BIDDER_ID, REQUIREMENT_ID, TENDER_ID, make_evidence

evaluator = DateEvaluator()

# ---------------------------------------------------------------------------
# Shared reference dates
# ---------------------------------------------------------------------------
DEADLINE = date(2026, 9, 15)       # tender deadline
BEFORE   = date(2026, 9, 10)       # 5 days before deadline
AFTER    = date(2026, 9, 20)       # 5 days after deadline
ONE_BEFORE = date(2026, 9, 14)     # one day before deadline (boundary)
ONE_AFTER  = date(2026, 9, 16)     # one day after deadline  (boundary)

FY_START = date(2023, 4, 1)        # financial year start
FY_END   = date(2026, 3, 31)       # financial year end


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_date_req(
    operator: Operator,
    required_value,
    field: str = "certificate_date",
) -> Requirement:
    return Requirement(
        requirement_id=REQUIREMENT_ID,
        tender_id=TENDER_ID,
        category=RequirementType.EXPERIENCE,
        field=field,
        rule_type=RuleType.DATE_RANGE,
        rule_definition=RuleDefinition(
            operator=operator,
            required_value=required_value,
        ),
    )


# ===========================================================================
# DATE_BEFORE  (actual < reference  — exclusive)
# ===========================================================================

class TestDateBefore:

    def test_before_deadline_pass(self):
        """Certificate 2026-09-10 before deadline 2026-09-15 → PASS."""
        req = make_date_req(Operator.DATE_BEFORE, DEADLINE)
        ev  = make_evidence("certificate_date", BEFORE)
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.PASS
        assert "before" in result.reason
        assert "2026-09-10" in result.reason
        assert "2026-09-15" in result.reason

    def test_after_deadline_fail(self):
        """Certificate 2026-09-20 NOT before 2026-09-15 → FAIL."""
        req = make_date_req(Operator.DATE_BEFORE, DEADLINE)
        ev  = make_evidence("certificate_date", AFTER)
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.FAIL
        assert "NOT" in result.reason

    def test_exact_deadline_fail(self):
        """Exact deadline (2026-09-15 < 2026-09-15) is FALSE → FAIL (exclusive)."""
        req = make_date_req(Operator.DATE_BEFORE, DEADLINE)
        ev  = make_evidence("certificate_date", DEADLINE)
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.FAIL

    def test_one_day_before_boundary_pass(self):
        """2026-09-14 < 2026-09-15 → PASS."""
        req = make_date_req(Operator.DATE_BEFORE, DEADLINE)
        ev  = make_evidence("certificate_date", ONE_BEFORE)
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.PASS

    def test_one_day_after_boundary_fail(self):
        """2026-09-16 < 2026-09-15 is FALSE → FAIL."""
        req = make_date_req(Operator.DATE_BEFORE, DEADLINE)
        ev  = make_evidence("certificate_date", ONE_AFTER)
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.FAIL


# ===========================================================================
# DATE_BEFORE_OR_EQUAL  (actual <= reference  — inclusive)
# ===========================================================================

class TestDateBeforeOrEqual:

    def test_before_pass(self):
        req = make_date_req(Operator.DATE_BEFORE_OR_EQUAL, DEADLINE)
        ev  = make_evidence("certificate_date", BEFORE)
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.PASS

    def test_exact_deadline_pass(self):
        """date <= deadline where date == deadline → PASS (inclusive)."""
        req = make_date_req(Operator.DATE_BEFORE_OR_EQUAL, DEADLINE)
        ev  = make_evidence("certificate_date", DEADLINE)
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.PASS
        assert "on or before" in result.reason

    def test_one_day_after_fail(self):
        """2026-09-16 <= 2026-09-15 → FAIL."""
        req = make_date_req(Operator.DATE_BEFORE_OR_EQUAL, DEADLINE)
        ev  = make_evidence("certificate_date", ONE_AFTER)
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.FAIL

    def test_long_before_pass(self):
        req = make_date_req(Operator.DATE_BEFORE_OR_EQUAL, DEADLINE)
        ev  = make_evidence("certificate_date", date(2020, 1, 1))
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.PASS


# ===========================================================================
# DATE_AFTER  (actual > reference  — exclusive)
# ===========================================================================

class TestDateAfter:

    def test_after_reference_pass(self):
        """Experience end date 2026-09-20 > 2026-09-15 → PASS."""
        req = make_date_req(Operator.DATE_AFTER, DEADLINE, field="experience_end_date")
        ev  = make_evidence("experience_end_date", AFTER)
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.PASS
        assert "after" in result.reason

    def test_before_reference_fail(self):
        req = make_date_req(Operator.DATE_AFTER, DEADLINE, field="experience_end_date")
        ev  = make_evidence("experience_end_date", BEFORE)
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.FAIL

    def test_exact_reference_fail(self):
        """Exact equality is NOT > → FAIL (exclusive)."""
        req = make_date_req(Operator.DATE_AFTER, DEADLINE, field="experience_end_date")
        ev  = make_evidence("experience_end_date", DEADLINE)
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.FAIL

    def test_one_day_after_boundary_pass(self):
        req = make_date_req(Operator.DATE_AFTER, DEADLINE, field="experience_end_date")
        ev  = make_evidence("experience_end_date", ONE_AFTER)
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.PASS


# ===========================================================================
# DATE_AFTER_OR_EQUAL  (actual >= reference  — inclusive)
# ===========================================================================

class TestDateAfterOrEqual:

    def test_after_pass(self):
        req = make_date_req(Operator.DATE_AFTER_OR_EQUAL, DEADLINE, field="experience_end_date")
        ev  = make_evidence("experience_end_date", AFTER)
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.PASS

    def test_exact_reference_pass(self):
        """Exact equality with >= → PASS (inclusive)."""
        req = make_date_req(Operator.DATE_AFTER_OR_EQUAL, DEADLINE, field="experience_end_date")
        ev  = make_evidence("experience_end_date", DEADLINE)
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.PASS
        assert "on or after" in result.reason

    def test_before_fail(self):
        req = make_date_req(Operator.DATE_AFTER_OR_EQUAL, DEADLINE, field="experience_end_date")
        ev  = make_evidence("experience_end_date", BEFORE)
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.FAIL

    def test_one_day_before_boundary_fail(self):
        req = make_date_req(Operator.DATE_AFTER_OR_EQUAL, DEADLINE, field="experience_end_date")
        ev  = make_evidence("experience_end_date", ONE_BEFORE)
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.FAIL


# ===========================================================================
# DATE_EQUAL
# ===========================================================================

class TestDateEqual:

    def test_same_date_pass(self):
        req = make_date_req(Operator.DATE_EQUAL, DEADLINE)
        ev  = make_evidence("certificate_date", DEADLINE)
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.PASS
        assert "equal to" in result.reason

    def test_different_date_fail(self):
        req = make_date_req(Operator.DATE_EQUAL, DEADLINE)
        ev  = make_evidence("certificate_date", BEFORE)
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.FAIL

    def test_one_day_off_fail(self):
        req = make_date_req(Operator.DATE_EQUAL, DEADLINE)
        ev  = make_evidence("certificate_date", ONE_BEFORE)
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.FAIL


# ===========================================================================
# DATE_BETWEEN  (inclusive on both ends: start <= actual <= end)
# ===========================================================================

class TestDateBetween:

    def test_in_range_pass(self):
        req = Requirement(
            requirement_id=REQUIREMENT_ID, tender_id=TENDER_ID,
            category="EXPERIENCE", field="experience_date",
            rule_type=RuleType.DATE_RANGE,
            rule_definition=RuleDefinition(
                operator=Operator.DATE_BETWEEN,
                required_value=[FY_START, FY_END],
            ),
        )
        ev = make_evidence("experience_date", date(2025, 6, 15))
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.PASS
        assert "within the" in result.reason
        assert "2025-06-15" in result.reason

    def test_on_start_bound_pass(self):
        """start <= actual: equality at start is PASS (inclusive)."""
        req = Requirement(
            requirement_id=REQUIREMENT_ID, tender_id=TENDER_ID,
            category="EXPERIENCE", field="experience_date",
            rule_type=RuleType.DATE_RANGE,
            rule_definition=RuleDefinition(
                operator=Operator.DATE_BETWEEN,
                required_value=[FY_START, FY_END],
            ),
        )
        ev = make_evidence("experience_date", FY_START)
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.PASS

    def test_on_end_bound_pass(self):
        """actual <= end: equality at end is PASS (inclusive)."""
        req = Requirement(
            requirement_id=REQUIREMENT_ID, tender_id=TENDER_ID,
            category="EXPERIENCE", field="experience_date",
            rule_type=RuleType.DATE_RANGE,
            rule_definition=RuleDefinition(
                operator=Operator.DATE_BETWEEN,
                required_value=[FY_START, FY_END],
            ),
        )
        ev = make_evidence("experience_date", FY_END)
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.PASS

    def test_one_day_before_start_fail(self):
        req = Requirement(
            requirement_id=REQUIREMENT_ID, tender_id=TENDER_ID,
            category="EXPERIENCE", field="experience_date",
            rule_type=RuleType.DATE_RANGE,
            rule_definition=RuleDefinition(
                operator=Operator.DATE_BETWEEN,
                required_value=[FY_START, FY_END],
            ),
        )
        ev = make_evidence("experience_date", FY_START - timedelta(days=1))
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.FAIL
        assert "NOT" in result.reason

    def test_one_day_after_end_fail(self):
        req = Requirement(
            requirement_id=REQUIREMENT_ID, tender_id=TENDER_ID,
            category="EXPERIENCE", field="experience_date",
            rule_type=RuleType.DATE_RANGE,
            rule_definition=RuleDefinition(
                operator=Operator.DATE_BETWEEN,
                required_value=[FY_START, FY_END],
            ),
        )
        ev = make_evidence("experience_date", FY_END + timedelta(days=1))
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.FAIL

    def test_point_range_start_eq_end_on_date_pass(self):
        """Single-day range where start == end. Exact match → PASS."""
        single_day = date(2025, 6, 15)
        req = Requirement(
            requirement_id=REQUIREMENT_ID, tender_id=TENDER_ID,
            category="EXPERIENCE", field="experience_date",
            rule_type=RuleType.DATE_RANGE,
            rule_definition=RuleDefinition(
                operator=Operator.DATE_BETWEEN,
                required_value=[single_day, single_day],
            ),
        )
        ev = make_evidence("experience_date", single_day)
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.PASS

    def test_point_range_off_by_one_fail(self):
        single_day = date(2025, 6, 15)
        req = Requirement(
            requirement_id=REQUIREMENT_ID, tender_id=TENDER_ID,
            category="EXPERIENCE", field="experience_date",
            rule_type=RuleType.DATE_RANGE,
            rule_definition=RuleDefinition(
                operator=Operator.DATE_BETWEEN,
                required_value=[single_day, single_day],
            ),
        )
        ev = make_evidence("experience_date", single_day + timedelta(days=1))
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.FAIL

    def test_invalid_between_single_value_review(self):
        """required_value is a single date, not [start, end] → REVIEW."""
        req = Requirement(
            requirement_id=REQUIREMENT_ID, tender_id=TENDER_ID,
            category="EXPERIENCE", field="experience_date",
            rule_type=RuleType.DATE_RANGE,
            rule_definition=RuleDefinition(
                operator=Operator.DATE_BETWEEN,
                required_value=FY_START,           # not a pair
            ),
        )
        ev = make_evidence("experience_date", date(2025, 6, 15))
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.REVIEW
        assert "misconfigured" in result.reason.lower()

    def test_between_with_string_bounds_pass(self):
        """ISO string bounds should be coerced and work correctly."""
        req = Requirement(
            requirement_id=REQUIREMENT_ID, tender_id=TENDER_ID,
            category="EXPERIENCE", field="experience_date",
            rule_type=RuleType.DATE_RANGE,
            rule_definition=RuleDefinition(
                operator=Operator.DATE_BETWEEN,
                required_value=["2023-04-01", "2026-03-31"],
            ),
        )
        ev = make_evidence("experience_date", "2025-06-15")
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.PASS


# ===========================================================================
# datetime / date compatibility
# ===========================================================================

class TestDatetimeDateCompatibility:

    def test_datetime_evidence_with_date_reference_pass(self):
        """datetime evidence is normalised to date before comparison."""
        req = make_date_req(Operator.DATE_BEFORE_OR_EQUAL, DEADLINE)
        dt_evidence = datetime(2026, 9, 10, 14, 30, 0)   # naive datetime
        ev = make_evidence("certificate_date", dt_evidence)
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.PASS

    def test_aware_datetime_evidence_pass(self):
        """Timezone-aware datetime is also coerced to date."""
        req = make_date_req(Operator.DATE_BEFORE_OR_EQUAL, DEADLINE)
        aware_dt = datetime(2026, 9, 10, 23, 59, 0, tzinfo=timezone.utc)
        ev = make_evidence("certificate_date", aware_dt)
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.PASS

    def test_date_evidence_with_datetime_reference_pass(self):
        """date evidence vs datetime required_value — required_value is coerced too."""
        req = make_date_req(
            Operator.DATE_BEFORE_OR_EQUAL,
            datetime(2026, 9, 15, 23, 59, 59),
        )
        ev = make_evidence("certificate_date", date(2026, 9, 10))
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.PASS

    def test_datetime_equal_to_date_pass(self):
        """datetime(2026, 9, 15, …) normalised to date(2026, 9, 15) == date(2026, 9, 15)."""
        req = make_date_req(Operator.DATE_EQUAL, DEADLINE)
        ev  = make_evidence("certificate_date", datetime(2026, 9, 15, 0, 0, 0))
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.PASS


# ===========================================================================
# ISO 8601 string inputs
# ===========================================================================

class TestISOStringInputs:

    def test_iso_date_string_evidence_pass(self):
        req = make_date_req(Operator.DATE_BEFORE_OR_EQUAL, DEADLINE)
        ev  = make_evidence("certificate_date", "2026-09-10")
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.PASS

    def test_iso_datetime_string_evidence_pass(self):
        req = make_date_req(Operator.DATE_BEFORE_OR_EQUAL, DEADLINE)
        ev  = make_evidence("certificate_date", "2026-09-10T14:30:00")
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.PASS

    def test_iso_date_string_on_boundary_pass(self):
        req = make_date_req(Operator.DATE_BEFORE_OR_EQUAL, DEADLINE)
        ev  = make_evidence("certificate_date", "2026-09-15")
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.PASS

    def test_iso_date_string_required_value_pass(self):
        """required_value as ISO string is also coerced."""
        req = make_date_req(Operator.DATE_BEFORE_OR_EQUAL, "2026-09-15")
        ev  = make_evidence("certificate_date", date(2026, 9, 10))
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.PASS

    def test_alternative_date_format_dmy_slash_pass(self):
        """DD/MM/YYYY format is accepted."""
        req = make_date_req(Operator.DATE_BEFORE_OR_EQUAL, DEADLINE)
        ev  = make_evidence("certificate_date", "10/09/2026")
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.PASS

    def test_alternative_date_format_dmy_dash_pass(self):
        """DD-MM-YYYY format is accepted."""
        req = make_date_req(Operator.DATE_BEFORE_OR_EQUAL, DEADLINE)
        ev  = make_evidence("certificate_date", "10-09-2026")
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.PASS


# ===========================================================================
# Missing / None evidence
# ===========================================================================

class TestMissingEvidence:

    def test_none_evidence_object_review(self):
        req = make_date_req(Operator.DATE_BEFORE_OR_EQUAL, DEADLINE)
        result = evaluator.evaluate(req, None)
        assert result.status == ComplianceStatus.REVIEW
        assert "No date evidence" in result.reason

    def test_none_evidence_value_review(self):
        req = make_date_req(Operator.DATE_BEFORE_OR_EQUAL, DEADLINE)
        ev  = make_evidence("certificate_date", None)
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.REVIEW

    def test_missing_required_value_review(self):
        req = make_date_req(Operator.DATE_BEFORE_OR_EQUAL, None)
        ev  = make_evidence("certificate_date", BEFORE)
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.REVIEW
        assert "missing" in result.reason.lower()


# ===========================================================================
# Malformed / invalid date evidence
# ===========================================================================

class TestMalformedDates:

    def test_random_string_review(self):
        req = make_date_req(Operator.DATE_BEFORE_OR_EQUAL, DEADLINE)
        ev  = make_evidence("certificate_date", "not-a-date")
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.REVIEW
        assert "could not be interpreted" in result.reason

    def test_integer_value_review(self):
        """Plain integers cannot be unambiguously interpreted as dates."""
        req = make_date_req(Operator.DATE_BEFORE_OR_EQUAL, DEADLINE)
        ev  = make_evidence("certificate_date", 20260910)
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.REVIEW

    def test_partial_date_string_review(self):
        """'2026-09' is not a complete date."""
        req = make_date_req(Operator.DATE_BEFORE_OR_EQUAL, DEADLINE)
        ev  = make_evidence("certificate_date", "2026-09")
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.REVIEW

    def test_empty_string_review(self):
        req = make_date_req(Operator.DATE_BEFORE_OR_EQUAL, DEADLINE)
        ev  = make_evidence("certificate_date", "")
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.REVIEW

    def test_invalid_required_value_review(self):
        """required_value that cannot be coerced → REVIEW (misconfigured rule)."""
        req = make_date_req(Operator.DATE_BEFORE_OR_EQUAL, "not-a-date")
        ev  = make_evidence("certificate_date", BEFORE)
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.REVIEW
        assert "misconfigured" in result.reason.lower()

    def test_list_evidence_value_review(self):
        req = make_date_req(Operator.DATE_BEFORE_OR_EQUAL, DEADLINE)
        ev  = make_evidence("certificate_date", [BEFORE, AFTER])
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.REVIEW

    def test_bool_evidence_value_review(self):
        req = make_date_req(Operator.DATE_BEFORE_OR_EQUAL, DEADLINE)
        ev  = make_evidence("certificate_date", True)
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.REVIEW


# ===========================================================================
# Low confidence
# ===========================================================================

class TestLowConfidence:

    def test_low_confidence_review(self):
        req = make_date_req(Operator.DATE_BEFORE_OR_EQUAL, DEADLINE)
        ev  = make_evidence("certificate_date", BEFORE, confidence=0.3)
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.REVIEW
        assert "low extraction confidence" in result.reason.lower()

    def test_exact_threshold_passes(self):
        """confidence == LOW_CONFIDENCE_THRESHOLD (0.5) is acceptable."""
        from app.compliance.evaluator import LOW_CONFIDENCE_THRESHOLD
        req = make_date_req(Operator.DATE_BEFORE_OR_EQUAL, DEADLINE)
        ev  = make_evidence("certificate_date", BEFORE, confidence=LOW_CONFIDENCE_THRESHOLD)
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.PASS

    def test_just_below_threshold_review(self):
        req = make_date_req(Operator.DATE_BEFORE_OR_EQUAL, DEADLINE)
        ev  = make_evidence("certificate_date", BEFORE, confidence=0.49)
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.REVIEW


# ===========================================================================
# Invalid operators
# ===========================================================================

class TestInvalidOperators:

    def test_numeric_operator_on_date_field_review(self):
        """GTE is meaningless for date fields in DateEvaluator."""
        req = make_date_req(Operator.GREATER_THAN_OR_EQUAL, DEADLINE)
        ev  = make_evidence("certificate_date", BEFORE)
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.REVIEW
        assert "not a date operator" in result.reason.lower()

    def test_minimum_on_date_review(self):
        req = make_date_req(Operator.MINIMUM, DEADLINE)
        ev  = make_evidence("certificate_date", BEFORE)
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.REVIEW

    def test_equal_on_date_review(self):
        """EQUAL (numeric) is not DATE_EQUAL — DateEvaluator should REVIEW."""
        req = make_date_req(Operator.EQUAL, DEADLINE)
        ev  = make_evidence("certificate_date", DEADLINE)
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.REVIEW


# ===========================================================================
# Result audit fields
# ===========================================================================

class TestAuditFields:

    def test_actual_value_is_date_object(self):
        req = make_date_req(Operator.DATE_BEFORE_OR_EQUAL, DEADLINE)
        ev  = make_evidence("certificate_date", BEFORE)
        result = evaluator.evaluate(req, ev)
        assert isinstance(result.actual_value, date)
        assert result.actual_value == BEFORE

    def test_required_value_is_date_object(self):
        req = make_date_req(Operator.DATE_BEFORE_OR_EQUAL, DEADLINE)
        ev  = make_evidence("certificate_date", BEFORE)
        result = evaluator.evaluate(req, ev)
        assert isinstance(result.required_value, date)
        assert result.required_value == DEADLINE

    def test_rule_type_stored(self):
        req = make_date_req(Operator.DATE_AFTER, DEADLINE, field="experience_end_date")
        ev  = make_evidence("experience_end_date", AFTER)
        result = evaluator.evaluate(req, ev)
        assert result.rule_type == RuleType.DATE_RANGE

    def test_operator_stored(self):
        req = make_date_req(Operator.DATE_AFTER_OR_EQUAL, DEADLINE, field="experience_end_date")
        ev  = make_evidence("experience_end_date", AFTER)
        result = evaluator.evaluate(req, ev)
        assert result.operator_used == Operator.DATE_AFTER_OR_EQUAL

    def test_evidence_reference_stored(self):
        req = make_date_req(Operator.DATE_BEFORE_OR_EQUAL, DEADLINE)
        ev  = make_evidence("certificate_date", BEFORE)
        result = evaluator.evaluate(req, ev)
        assert result.evidence_reference == "test_doc.pdf"

    def test_between_actual_value_stored(self):
        req = Requirement(
            requirement_id=REQUIREMENT_ID, tender_id=TENDER_ID,
            category="EXPERIENCE", field="experience_date",
            rule_type=RuleType.DATE_RANGE,
            rule_definition=RuleDefinition(
                operator=Operator.DATE_BETWEEN,
                required_value=[FY_START, FY_END],
            ),
        )
        ev = make_evidence("experience_date", date(2025, 6, 15))
        result = evaluator.evaluate(req, ev)
        assert result.actual_value == date(2025, 6, 15)
        assert result.required_value == [FY_START, FY_END]

