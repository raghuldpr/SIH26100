from app.models.enums import (
    BidderStatus,
    DocumentProcessingStatus,
    DocumentStatus,
    DocumentType,
    ProcessingStatus,
    RequirementType,
    TenderStatus,
    UserRole,
)

try:
    from app.models.bidder import Bidder, TenderBidder
    from app.models.document import Document
    from app.models.compliance import (
        BidderEvidenceModel,
        ComplianceRequirement,
        ComplianceResultModel,
    )
    from app.models.tender import Tender
    from app.models.tender_requirement import TenderRequirement
    from app.models.user import User
    from app.models.verification import (
        VerificationAuditEvent,
        VerificationExecution,
    )
except ImportError:
    Bidder = None  # type: ignore
    TenderBidder = None  # type: ignore
    Document = None  # type: ignore
    BidderEvidenceModel = None  # type: ignore
    ComplianceRequirement = None  # type: ignore
    ComplianceResultModel = None  # type: ignore
    Tender = None  # type: ignore
    TenderRequirement = None  # type: ignore
    User = None  # type: ignore
    VerificationExecution = None  # type: ignore
    VerificationAuditEvent = None  # type: ignore

__all__ = [
    "User",
    "Tender",
    "Bidder",
    "TenderBidder",
    "Document",
    "TenderRequirement",
    "ComplianceRequirement",
    "BidderEvidenceModel",
    "ComplianceResultModel",
    "VerificationExecution",
    "VerificationAuditEvent",
    "UserRole",
    "TenderStatus",
    "BidderStatus",
    "DocumentType",
    "DocumentStatus",
    "ProcessingStatus",
    "DocumentProcessingStatus",
    "RequirementType",
]



