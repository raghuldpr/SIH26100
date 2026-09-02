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
    OPEN = "OPEN"
    PUBLISHED = "PUBLISHED"
    EVALUATING = "EVALUATING"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"
    ARCHIVED = "ARCHIVED"


class BidderStatus(str, enum.Enum):
    """Bidder operational and eligibility states."""
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUSPENDED = "SUSPENDED"


class DocumentType(str, enum.Enum):
    """Document classification types for Tenders and Bidders."""
    # Tender Documents
    TENDER = "TENDER"
    TENDER_PDF = "TENDER_PDF"
    TENDER_NOTICE = "TENDER_NOTICE"
    TECHNICAL_BID = "TECHNICAL_BID"
    FINANCIAL_BID = "FINANCIAL_BID"
    COMPLIANCE_DECLARATION = "COMPLIANCE_DECLARATION"
    CERTIFICATE = "CERTIFICATE"
    
    # Bidder Compliance & Verification Documents
    PAN = "PAN"
    GST = "GST"
    UDYAM = "UDYAM"
    FINANCIAL_STATEMENT = "FINANCIAL_STATEMENT"
    EXPERIENCE_CERTIFICATE = "EXPERIENCE_CERTIFICATE"
    OEM_AUTHORIZATION = "OEM_AUTHORIZATION"
    MII_DECLARATION = "MII_DECLARATION"
    TURNOVER = "TURNOVER"
    EXPERIENCE = "EXPERIENCE"
    OTHER = "OTHER"


class DocumentStatus(str, enum.Enum):
    """Lifecycle status of an uploaded document artifact."""
    ACTIVE = "ACTIVE"
    DELETED = "DELETED"
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    ARCHIVED = "ARCHIVED"


class ProcessingStatus(str, enum.Enum):
    """Document processing and OCR / compliance extraction lifecycle status."""
    NOT_PROCESSED = "NOT_PROCESSED"
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    EXTRACTED = "EXTRACTED"
    OCR_REQUIRED = "OCR_REQUIRED"
    OCR_COMPLETED = "OCR_COMPLETED"
    PARTIALLY_EXTRACTED = "PARTIALLY_EXTRACTED"
    FAILED = "FAILED"


DocumentProcessingStatus = ProcessingStatus


class RequirementType(str, enum.Enum):
    """Classification types for tender eligibility and compliance requirements."""
    FINANCIAL = "FINANCIAL"
    EXPERIENCE = "EXPERIENCE"
    TECHNICAL = "TECHNICAL"
    STATUTORY = "STATUTORY"
    DOCUMENT = "DOCUMENT"
    OEM = "OEM"
    MII = "MII"
    MSE = "MSE"
    STARTUP = "STARTUP"
    EXEMPTION = "EXEMPTION"
    OTHER = "OTHER"

