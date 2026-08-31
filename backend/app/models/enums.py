import enum


class UserRole(str, enum.Enum):
    """User access control roles."""
    PROCUREMENT_OFFICER = "PROCUREMENT_OFFICER"
    ADMIN = "ADMIN"
    REVIEWER = "REVIEWER"
    BUYER = "BUYER"
    BIDDER = "BIDDER"



class TenderStatus(str, enum.Enum):
    """Tender procurement lifecycle states."""
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    EVALUATING = "EVALUATING"
    CLOSED = "CLOSED"
    ARCHIVED = "ARCHIVED"


class DocumentType(str, enum.Enum):
    """Document classification types."""
    TENDER_NOTICE = "TENDER_NOTICE"
    TECHNICAL_BID = "TECHNICAL_BID"
    FINANCIAL_BID = "FINANCIAL_BID"
    COMPLIANCE_DECLARATION = "COMPLIANCE_DECLARATION"
    CERTIFICATE = "CERTIFICATE"
    OTHER = "OTHER"
