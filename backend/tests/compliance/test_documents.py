"""
Phase 09 — Compliance Rule Engine
tests/compliance/test_documents.py: Comprehensive DocumentEvaluator tests.

Test matrix
-----------
1. Mandatory document present & verified → PASS
2. Mandatory document missing → FAIL
3. Optional document missing → NOT_APPLICABLE (collapses to PASS externally)
4. Document ambiguous (status=AMBIGUOUS, PENDING, or confidence < 0.5) → REVIEW
5. Document verification failure (status=FAILED, INVALID, REJECTED) → FAIL
6. Exempt bidder (is_exempt=True, status=EXEMPT) → EXEMPT (collapses to PASS externally)
7. Wrong document type (submitted PAN when GST required) → FAIL
8. Multiple candidate documents (one valid among several, all wrong, one ambiguous)
9. Format variations (boolean value, string value, dict value, candidate list)
10. Audit fields preservation
"""
from __future__ import annotations

import uuid
import pytest

from app.compliance.documents import DocumentEvaluator
from app.compliance.enums import ComplianceStatus, Operator, RuleType
from app.compliance.models import BidderEvidence, ComplianceResult, Requirement, RuleDefinition
from app.models.enums import RequirementType

from tests.compliance.conftest import BIDDER_ID, REQUIREMENT_ID, TENDER_ID, make_evidence

evaluator = DocumentEvaluator()
S = ComplianceStatus


def make_doc_req(
    field: str = "gst_certificate",
    document_type: str = "GST_CERTIFICATE",
    mandatory: bool = True,
    operator: Operator = Operator.PRESENT,
) -> Requirement:
    return Requirement(
        requirement_id=REQUIREMENT_ID,
        tender_id=TENDER_ID,
        category=RequirementType.DOCUMENT,
        field=field,
        rule_type=RuleType.DOCUMENT_PRESENCE,
        mandatory=mandatory,
        rule_definition=RuleDefinition(
            operator=operator,
            required_value=document_type,
        ),
    )


# ===========================================================================
# 1. Mandatory Document Present & Verified
# ===========================================================================

class TestMandatoryDocumentPresent:

    def test_document_dict_verified_pass(self):
        req = make_doc_req("gst_certificate", "GST_CERTIFICATE")
        ev = make_evidence(
            "gst_certificate",
            {
                "document_type": "GST_CERTIFICATE",
                "document_name": "gst_registration.pdf",
                "verification_status": "VERIFIED",
                "confidence": 0.95,
            },
        )
        result = evaluator.evaluate(req, ev)
        assert result.status == S.PASS
        assert result.is_pass is True
        assert "present and verified" in result.reason


    def test_document_boolean_true_pass(self):
        req = make_doc_req("pan_document", "PAN")
        ev = make_evidence("pan_document", True, confidence=0.9)
        result = evaluator.evaluate(req, ev)
        assert result.status == S.PASS

    def test_document_filename_string_pass(self):
        req = make_doc_req("pan_document", "PAN")
        ev = make_evidence("pan_document", "pan_card.pdf", confidence=0.9)
        result = evaluator.evaluate(req, ev)
        assert result.status == S.PASS


# ===========================================================================
# 2. Mandatory Document Missing
# ===========================================================================

class TestMandatoryDocumentMissing:

    def test_none_evidence_mandatory_fails(self):
        req = make_doc_req("gst_certificate", "GST_CERTIFICATE", mandatory=True)
        result = evaluator.evaluate(req, None)
        assert result.status == S.FAIL
        assert result.is_fail is True
        assert "definitely absent" in result.reason

    def test_none_value_mandatory_fails(self):
        req = make_doc_req("gst_certificate", "GST_CERTIFICATE", mandatory=True)
        ev = make_evidence("gst_certificate", None)
        result = evaluator.evaluate(req, ev)
        assert result.status == S.FAIL

    def test_boolean_false_mandatory_fails(self):
        req = make_doc_req("gst_certificate", "GST_CERTIFICATE", mandatory=True)
        ev = make_evidence("gst_certificate", False)
        result = evaluator.evaluate(req, ev)
        assert result.status == S.FAIL

    def test_explicit_absent_status_mandatory_fails(self):
        req = make_doc_req("gst_certificate", "GST_CERTIFICATE", mandatory=True)
        ev = make_evidence("gst_certificate", {"verification_status": "ABSENT"})
        result = evaluator.evaluate(req, ev)
        assert result.status == S.FAIL


# ===========================================================================
# 3. Optional Document Missing
# ===========================================================================

class TestOptionalDocumentMissing:

    def test_none_evidence_optional_not_applicable(self):
        req = make_doc_req("iso_certificate", "ISO_CERTIFICATE", mandatory=False)
        result = evaluator.evaluate(req, None)
        assert result.status == S.NOT_APPLICABLE
        assert result.external_status == S.PASS
        assert result.is_pass is True

    def test_explicit_absent_optional_not_applicable(self):
        req = make_doc_req("iso_certificate", "ISO_CERTIFICATE", mandatory=False)
        ev = make_evidence("iso_certificate", {"verification_status": "ABSENT"})
        result = evaluator.evaluate(req, ev)
        assert result.status == S.NOT_APPLICABLE


# ===========================================================================
# 4. Document Ambiguous / Low Confidence
# ===========================================================================

class TestDocumentAmbiguous:

    def test_status_ambiguous_gives_review(self):
        req = make_doc_req("gst_certificate", "GST_CERTIFICATE")
        ev = make_evidence(
            "gst_certificate",
            {
                "document_type": "GST_CERTIFICATE",
                "verification_status": "AMBIGUOUS",
                "confidence": 0.8,
            },
        )
        result = evaluator.evaluate(req, ev)
        assert result.status == S.REVIEW
        assert result.is_review is True
        assert "cannot be confidently identified or verified" in result.reason

    def test_status_pending_gives_review(self):
        req = make_doc_req("gst_certificate", "GST_CERTIFICATE")
        ev = make_evidence(
            "gst_certificate",
            {
                "document_type": "GST_CERTIFICATE",
                "verification_status": "PENDING",
            },
        )
        result = evaluator.evaluate(req, ev)
        assert result.status == S.REVIEW

    def test_low_confidence_gives_review(self):
        req = make_doc_req("gst_certificate", "GST_CERTIFICATE")
        ev = make_evidence(
            "gst_certificate",
            {
                "document_type": "GST_CERTIFICATE",
                "verification_status": "VERIFIED",
                "confidence": 0.35,  # Low confidence
            },
            confidence=0.35,
        )
        result = evaluator.evaluate(req, ev)
        assert result.status == S.REVIEW


# ===========================================================================
# 5. Document Verification Failure
# ===========================================================================

class TestDocumentVerificationFailure:

    def test_status_failed_gives_fail(self):
        req = make_doc_req("gst_certificate", "GST_CERTIFICATE")
        ev = make_evidence(
            "gst_certificate",
            {
                "document_type": "GST_CERTIFICATE",
                "verification_status": "FAILED",
                "rejection_reason": "Digital signature verification failed",
            },
        )
        result = evaluator.evaluate(req, ev)
        assert result.status == S.FAIL
        assert "verification failed" in result.reason.lower()

    def test_status_expired_gives_fail(self):
        req = make_doc_req("gst_certificate", "GST_CERTIFICATE")
        ev = make_evidence(
            "gst_certificate",
            {
                "document_type": "GST_CERTIFICATE",
                "verification_status": "EXPIRED",
                "rejection_reason": "Certificate expired on 2024-01-01",
            },
        )
        result = evaluator.evaluate(req, ev)
        assert result.status == S.FAIL


# ===========================================================================
# 6. Exempt Bidder
# ===========================================================================

class TestExemptBidder:

    def test_is_exempt_flag_returns_exempt(self):
        req = make_doc_req("turnover_certificate", "TURNOVER_CERTIFICATE", mandatory=True)
        ev = make_evidence(
            "turnover_certificate",
            {
                "is_exempt": True,
                "exemption_reason": "Registered Micro Enterprise (MSE)",
            },
        )
        result = evaluator.evaluate(req, ev)
        assert result.status == S.EXEMPT
        assert result.external_status == S.PASS
        assert result.is_pass is True
        assert "EXEMPT" in result.reason

    def test_verification_status_exempt_returns_exempt(self):
        req = make_doc_req("emd_document", "EMD_RECEIPT", mandatory=True)
        ev = make_evidence(
            "emd_document",
            {
                "verification_status": "EXEMPT",
                "exemption_reason": "Startup India DPIIT Recognized",
            },
        )
        result = evaluator.evaluate(req, ev)
        assert result.status == S.EXEMPT


# ===========================================================================
# 7. Wrong Document Type
# ===========================================================================

class TestWrongDocumentType:

    def test_wrong_type_submitted_fails(self):
        req = make_doc_req("gst_certificate", "GST_CERTIFICATE")
        ev = make_evidence(
            "gst_certificate",
            {
                "document_type": "PAN_CARD",
                "verification_status": "VERIFIED",
            },
        )
        result = evaluator.evaluate(req, ev)
        assert result.status == S.FAIL
        assert "do not match the required document type" in result.reason

    def test_unrelated_document_fails(self):
        req = make_doc_req("pan_document", "PAN")
        ev = make_evidence(
            "pan_document",
            {
                "document_type": "DRIVING_LICENSE",
                "verification_status": "VERIFIED",
            },
        )
        result = evaluator.evaluate(req, ev)
        assert result.status == S.FAIL


# ===========================================================================
# 8. Multiple Candidate Documents
# ===========================================================================

class TestMultipleCandidateDocuments:

    def test_candidate_list_with_one_valid_passes(self):
        """Among multiple candidates, one matching verified doc yields PASS."""
        req = make_doc_req("gst_certificate", "GST_CERTIFICATE")
        candidates = [
            {"document_type": "PAN_CARD", "verification_status": "VERIFIED"},
            {"document_type": "GST_CERTIFICATE", "verification_status": "VERIFIED", "document_name": "valid_gst.pdf"},
        ]
        ev = make_evidence("gst_certificate", candidates)
        result = evaluator.evaluate(req, ev)
        assert result.status == S.PASS
        assert "present and verified" in result.reason

    def test_candidate_list_all_wrong_type_fails(self):
        req = make_doc_req("gst_certificate", "GST_CERTIFICATE")
        candidates = [
            {"document_type": "PAN_CARD", "verification_status": "VERIFIED"},
            {"document_type": "INCORPORATION_CERTIFICATE", "verification_status": "VERIFIED"},
        ]
        ev = make_evidence("gst_certificate", candidates)
        result = evaluator.evaluate(req, ev)
        assert result.status == S.FAIL
        assert "do not match" in result.reason

    def test_candidate_list_matching_but_ambiguous_gives_review(self):
        req = make_doc_req("gst_certificate", "GST_CERTIFICATE")
        candidates = [
            {"document_type": "PAN_CARD", "verification_status": "VERIFIED"},
            {"document_type": "GST_CERTIFICATE", "verification_status": "AMBIGUOUS"},
        ]
        ev = make_evidence("gst_certificate", candidates)
        result = evaluator.evaluate(req, ev)
        assert result.status == S.REVIEW

    def test_candidate_list_with_exemption(self):
        req = make_doc_req("gst_certificate", "GST_CERTIFICATE")
        candidates = [
            {"is_exempt": True, "exemption_reason": "Foreign Bidder Tax Treaty"},
        ]
        ev = make_evidence("gst_certificate", candidates)
        result = evaluator.evaluate(req, ev)
        assert result.status == S.EXEMPT


# ===========================================================================
# 9. Audit Fields
# ===========================================================================

class TestDocumentAuditFields:

    def test_rule_type_is_document_presence(self):
        req = make_doc_req("gst_certificate", "GST_CERTIFICATE")
        ev = make_evidence("gst_certificate", {"verification_status": "VERIFIED"})
        result = evaluator.evaluate(req, ev)
        assert result.rule_type == RuleType.DOCUMENT_PRESENCE

    def test_operator_used_stored(self):
        req = make_doc_req("gst_certificate", "GST_CERTIFICATE", operator=Operator.PRESENT)
        ev = make_evidence("gst_certificate", {"verification_status": "VERIFIED"})
        result = evaluator.evaluate(req, ev)
        assert result.operator_used == Operator.PRESENT

    def test_evidence_reference_stored(self):
        req = make_doc_req("gst_certificate", "GST_CERTIFICATE")
        ev = make_evidence(
            "gst_certificate",
            {"verification_status": "VERIFIED", "source_document": "docs/gst_cert.pdf"},
        )
        result = evaluator.evaluate(req, ev)
        assert result.evidence_reference == "docs/gst_cert.pdf"

