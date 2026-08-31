import re
from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class ClassificationRule:
    """Declarative definition of classification indicators and weights for a document type."""

    doc_type: str
    strong_phrases: List[Tuple[str, float]] = field(default_factory=list)
    keywords: List[Tuple[str, float]] = field(default_factory=list)
    patterns: List[Tuple[re.Pattern, str, float]] = field(default_factory=list)


# Precompiled Regex Patterns for Document Identifiers (case-insensitive)
PAN_REGEX = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b", re.IGNORECASE)
PAN_SPACED_REGEX = re.compile(
    r"\b[A-Z]\s+[A-Z]\s+[A-Z]\s+[A-Z]\s+[A-Z]\s+[0-9]\s+[0-9]\s+[0-9]\s+[0-9]\s+[A-Z]\b",
    re.IGNORECASE,
)
PAN_LABEL_REGEX = re.compile(r"\bP\s*A\s*N\b", re.IGNORECASE)

GSTIN_REGEX = re.compile(
    r"\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}\b", re.IGNORECASE
)
GSTIN_LABEL_REGEX = re.compile(r"\bG\s*S\s*T\s*I\s*N\b", re.IGNORECASE)

UDYAM_REGEX = re.compile(r"\bUDYAM-[A-Z]{2}-[0-9]{2}-[0-9]{7}\b", re.IGNORECASE)
UDYAM_LABEL_REGEX = re.compile(r"\bU\s*D\s*Y\s*A\s*M\b", re.IGNORECASE)

UDIN_REGEX = re.compile(r"\b[0-9]{2}[0-9]{6}[A-Z]{6}[0-9]{4}\b", re.IGNORECASE)
UDIN_LABEL_REGEX = re.compile(r"\bU\s*D\s*I\s*N\b", re.IGNORECASE)

GEM_BID_REGEX = re.compile(r"\bGEM/[0-9]{4}/[A-Z]/[0-9]+\b", re.IGNORECASE)


CLASSIFICATION_RULES: List[ClassificationRule] = [
    # 1. PAN (Permanent Account Number)
    ClassificationRule(
        doc_type="PAN",
        strong_phrases=[
            ("permanent account number", 3.5),
            ("income tax department", 3.0),
            ("govt. of india", 1.5),
            ("government of india", 1.5),
        ],
        keywords=[
            ("father's name", 1.5),
            ("fathers name", 1.5),
            ("date of birth", 1.2),
        ],
        patterns=[
            (PAN_REGEX, "PAN_NUMBER_PATTERN", 3.5),
            (PAN_SPACED_REGEX, "PAN_SPACED_PATTERN", 3.0),
            (PAN_LABEL_REGEX, "PAN_LABEL", 1.2),
        ],
    ),
    # 2. GST (Goods and Services Tax Certificate)
    ClassificationRule(
        doc_type="GST",
        strong_phrases=[
            ("goods and services tax", 3.5),
            ("central goods and services tax", 3.5),
            ("state goods and services tax", 3.5),
            ("gst registration certificate", 4.0),
            ("registration certificate", 2.0),
            ("form gst reg", 3.5),
        ],
        keywords=[
            ("gstin", 2.5),
            ("taxpayer", 1.2),
            ("date of liability", 1.5),
            ("jurisdiction", 1.0),
        ],
        patterns=[
            (GSTIN_REGEX, "GSTIN_PATTERN", 4.0),
            (GSTIN_LABEL_REGEX, "GSTIN_LABEL", 2.0),
        ],
    ),
    # 3. UDYAM (MSME Registration Certificate)
    ClassificationRule(
        doc_type="UDYAM",
        strong_phrases=[
            ("udyam registration certificate", 4.0),
            ("udyam registration number", 3.5),
            ("ministry of micro, small and medium enterprises", 3.5),
            ("ministry of msme", 3.0),
        ],
        keywords=[
            ("enterprise type", 1.5),
            ("major activity", 1.5),
            ("micro enterprise", 1.5),
            ("small enterprise", 1.5),
            ("medium enterprise", 1.5),
            ("nic 2 digit", 1.5),
        ],
        patterns=[
            (UDYAM_REGEX, "UDYAM_REGISTRATION_PATTERN", 4.0),
            (UDYAM_LABEL_REGEX, "UDYAM_LABEL", 1.5),
        ],
    ),
    # 4. FINANCIAL_STATEMENT (Audited Balance Sheet, P&L, Turnover, UDIN)
    ClassificationRule(
        doc_type="FINANCIAL_STATEMENT",
        strong_phrases=[
            ("balance sheet", 3.5),
            ("statement of profit and loss", 3.5),
            ("profit and loss account", 3.5),
            ("independent auditor's report", 3.5),
            ("independent auditors report", 3.5),
            ("auditors report", 3.0),
            ("chartered accountants", 2.0),
            ("cash flow statement", 3.0),
            ("annual turnover", 2.5),
            ("as at 31st march", 2.0),
        ],
        keywords=[
            ("financial year", 1.5),
            ("turnover", 1.2),
            ("current liabilities", 1.5),
            ("current assets", 1.5),
            ("revenue from operations", 2.0),
            ("net profit", 1.5),
        ],
        patterns=[
            (UDIN_REGEX, "UDIN_PATTERN", 3.5),
            (UDIN_LABEL_REGEX, "UDIN_LABEL", 1.5),
        ],
    ),
    # 5. EXPERIENCE_CERTIFICATE (Work Completion / Satisfactory Performance)
    ClassificationRule(
        doc_type="EXPERIENCE_CERTIFICATE",
        strong_phrases=[
            ("work completion certificate", 4.0),
            ("experience certificate", 4.0),
            ("satisfactorily completed", 3.5),
            ("execution of work", 3.0),
            ("performance certificate", 3.5),
            ("satisfactory execution", 3.0),
        ],
        keywords=[
            ("contract value", 1.8),
            ("purchase order", 1.5),
            ("work order", 1.5),
            ("period of contract", 1.5),
            ("scope of work", 1.5),
            ("date of completion", 1.5),
            ("executed value", 1.8),
        ],
        patterns=[],
    ),
    # 6. OEM_AUTHORIZATION (Manufacturer Authorization Form / MAF)
    ClassificationRule(
        doc_type="OEM_AUTHORIZATION",
        strong_phrases=[
            ("manufacturer's authorization form", 4.0),
            ("manufacturers authorization form", 4.0),
            ("manufacturer authorization", 3.5),
            ("oem authorization", 4.0),
            ("hereby authorize", 3.0),
            ("official manufacturer", 2.5),
            ("original equipment manufacturer", 3.0),
        ],
        keywords=[
            ("maf", 2.0),
            ("authorized partner", 2.0),
            ("bid against tender", 2.0),
            ("authorized dealer", 1.8),
            ("guarantee and warranty", 2.0),
            ("distributor", 1.2),
        ],
        patterns=[],
    ),
    # 7. MII_DECLARATION (Make in India / Local Content Declaration)
    ClassificationRule(
        doc_type="MII_DECLARATION",
        strong_phrases=[
            ("make in india", 3.5),
            ("local content", 3.5),
            ("public procurement (preference to make in india)", 4.0),
            ("preference to make in india", 3.5),
            ("class-i local supplier", 3.5),
            ("class-ii local supplier", 3.5),
            ("local value addition", 3.0),
            ("mii declaration", 4.0),
        ],
        keywords=[
            ("percentage of local content", 2.5),
            ("self-certification", 2.0),
            ("country of origin", 1.5),
            ("location of value addition", 2.0),
            ("dpiit order", 2.0),
        ],
        patterns=[],
    ),
    # 8. TENDER (GeM Bid Document / Notice Inviting Tender)
    ClassificationRule(
        doc_type="TENDER",
        strong_phrases=[
            ("gem bid document", 4.0),
            ("bid document", 3.0),
            ("notice inviting tender", 3.5),
            ("tender notice", 3.0),
            ("tender specification", 3.0),
            ("bid end date", 2.5),
            ("bid opening date", 2.5),
            ("consignee/reporting officer", 2.5),
        ],
        keywords=[
            ("tender number", 2.0),
            ("bid number", 2.0),
            ("earnest money deposit", 2.0),
            ("emd", 1.5),
            ("contract period", 1.5),
            ("buyer details", 1.5),
            ("ministry/state name", 1.5),
            ("item category", 1.5),
        ],
        patterns=[
            (GEM_BID_REGEX, "GEM_BID_NUMBER_PATTERN", 4.0),
        ],
    ),
]
