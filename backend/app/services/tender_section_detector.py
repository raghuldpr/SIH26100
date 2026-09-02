import logging
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from app.schemas.normalized_content import (
    NormalizedCurrency,
    NormalizedDate,
    NormalizedDocument,
    NormalizedNumber,
    NormalizedPage,
    NormalizedTable,
)
from app.schemas.processing import ExtractionResult
from app.schemas.tender_section import (
    DetectedTenderSection,
    SectionType,
    TenderSectionDetectionResult,
)
from app.services.content_normalizer import DocumentContentNormalizer, content_normalizer

logger = logging.getLogger("app.services.tender_section_detector")

# Section Detection Definition Rules: (SectionType, StandardName, RegexPattern, KeywordsList, BaseConfidence)
SECTION_DEFINITION_RULES = [
    # 1. Tender Information
    (
        SectionType.TENDER_INFORMATION,
        "Tender Information",
        re.compile(
            r"^(?:(?:SECTION|PART|CHAPTER|CLAUSE|ANNEXURE)\s+[IVXLCDM\d\.]+\s*[:\-\.]?\s*)?"
            r"(?:NOTICE\s+INVITING\s+TENDER|NIT|TENDER\s+INFORMATION|BID\s+INFORMATION|"
            r"GENERAL\s+INFORMATION|BID\s+DETAILS|CRITICAL\s+DATES|TENDER\s+SUMMARY|"
            r"PROJECT\s+OVERVIEW|INTRODUCTION|TENDER\s+NOTICE|INVITATION\s+FOR\s+BIDS?)\b",
            re.IGNORECASE,
        ),
        [
            "notice inviting tender", "nit", "tender information", "bid details",
            "critical dates", "tender notice", "general information", "overview",
            "invitation for bid", "ifb", "bid submission start date", "tender fee",
        ],
        0.95,
    ),
    # 2. Eligibility Criteria
    (
        SectionType.ELIGIBILITY_CRITERIA,
        "Eligibility Criteria",
        re.compile(
            r"^(?:(?:SECTION|PART|CHAPTER|CLAUSE|ANNEXURE)\s+[IVXLCDM\d\.]+\s*[:\-\.]?\s*)?"
            r"(?:ELIGIBILITY\s+CRITERIA|MINIMUM\s+ELIGIBILITY|QUALIFICATION\s+CRITERIA|"
            r"PRE-?QUALIFICATION\s+CRITERIA|ELIGIBILITY\s+CONDITIONS?|QUALIFYING\s+REQUIREMENTS?|"
            r"BIDDER\s+ELIGIBILITY|CRITERIA\s+FOR\s+ELIGIBILITY)\b",
            re.IGNORECASE,
        ),
        [
            "eligibility criteria", "minimum eligibility", "qualification criteria",
            "pre-qualification", "eligibility conditions", "qualifying requirements",
            "bidder must meet", "bidder eligibility",
        ],
        0.95,
    ),
    # 3. Technical Requirements
    (
        SectionType.TECHNICAL_REQUIREMENTS,
        "Technical Requirements",
        re.compile(
            r"^(?:(?:SECTION|PART|CHAPTER|CLAUSE|ANNEXURE)\s+[IVXLCDM\d\.]+\s*[:\-\.]?\s*)?"
            r"(?:TECHNICAL\s+REQUIREMENTS?|TECHNICAL\s+SPECIFICATIONS?|TECHNICAL\s+CRITERIA|"
            r"BILL\s+OF\s+MATERIALS?|BOM|TECHNICAL\s+SCHEDULE|TECHNICAL\s+BID\s+SPECIFICATIONS?|"
            r"HARDWARE\s+SPECIFICATIONS?|SOFTWARE\s+SPECIFICATIONS?|TECHNICAL\s+COMPLIANCE)\b",
            re.IGNORECASE,
        ),
        [
            "technical specifications", "technical requirements", "technical criteria",
            "bill of materials", "bom", "technical schedule", "technical compliance",
            "specifications of equipment", "specifications schedule",
        ],
        0.95,
    ),
    # 4. Financial Requirements
    (
        SectionType.FINANCIAL_REQUIREMENTS,
        "Financial Requirements",
        re.compile(
            r"^(?:(?:SECTION|PART|CHAPTER|CLAUSE|ANNEXURE)\s+[IVXLCDM\d\.]+\s*[:\-\.]?\s*)?"
            r"(?:(?:FINANCIAL|TURNOVER)\s+(?:REQUIREMENTS?|CRITERIA|CAPACITY|STANDING|ELIGIBILITY)|"
            r"ANNUAL\s+TURNOVER|NET\s+WORTH(?:\s+CRITERIA)?|SOLVENCY(?:\s+CRITERIA|\s+CERTIFICATE)?|"
            r"FINANCIAL\s+CAPACITY|AUDITED\s+FINANCIALS?)\b",
            re.IGNORECASE,
        ),
        [
            "financial criteria", "financial requirements", "turnover requirements",
            "annual turnover", "turnover criteria", "average turnover", "net worth",
            "solvency certificate", "financial standing", "audited balance sheet", "financial capacity",
        ],
        0.95,
    ),
    # 5. Experience
    (
        SectionType.EXPERIENCE,
        "Experience",
        re.compile(
            r"^(?:(?:SECTION|PART|CHAPTER|CLAUSE|ANNEXURE)\s+[IVXLCDM\d\.]+\s*[:\-\.]?\s*)?"
            r"(?:EXPERIENCE(?:\s+CRITERIA)?|PAST\s+EXPERIENCE|PAST\s+PERFORMANCE|"
            r"SIMILAR\s+WORKS?(?:\s+EXPERIENCE)?|WORK\s+EXPERIENCE|TRACK\s+RECORD|"
            r"EXPERIENCE\s+IN\s+SIMILAR\s+SUPPLY|PAST\s+EXECUTION)\b",
            re.IGNORECASE,
        ),
        [
            "past experience", "similar work experience", "work experience",
            "past performance", "similar works", "track record", "past contracts",
            "completed projects", "client satisfaction certificate",
        ],
        0.95,
    ),
    # 6. Statutory Requirements
    (
        SectionType.STATUTORY_REQUIREMENTS,
        "Statutory Requirements",
        re.compile(
            r"^(?:(?:SECTION|PART|CHAPTER|CLAUSE|ANNEXURE)\s+[IVXLCDM\d\.]+\s*[:\-\.]?\s*)?"
            r"(?:(?:GST|PAN|PF|ESI|TAX|STATUTORY|LEGAL|REGULATORY)\s+(?:REQUIREMENTS?|COMPLIANCE|REGISTRATIONS?|DECLARATIONS?|OBLIGATIONS?)|"
            r"LABOR\s+LAWS?\s+COMPLIANCE|STATUTORY\s+OBLIGATIONS?)\b",
            re.IGNORECASE,
        ),
        [
            "statutory requirements", "statutory compliance", "statutory registrations",
            "gst registration", "gst registrations", "gst and statutory registrations",
            "pan card", "pf registration", "esi registration", "labor laws",
            "statutory declaration", "msme udyam", "tax compliance",
        ],
        0.90,
    ),
    # 7. Required Documents
    (
        SectionType.REQUIRED_DOCUMENTS,
        "Required Documents",
        re.compile(
            r"^(?:(?:SECTION|PART|CHAPTER|CLAUSE|ANNEXURE)\s+[IVXLCDM\d\.]+\s*[:\-\.]?\s*)?"
            r"(?:REQUIRED\s+DOCUMENTS?|MANDATORY\s+DOCUMENTS?|CHECKLIST\s+OF\s+DOCUMENTS?|"
            r"DOCUMENTS\s+TO\s+BE\s+SUBMITTED|LIST\s+OF\s+DOCUMENTS?|SUBMISSION\s+CHECKLIST|"
            r"ENCLOSURES\s+REQUIRED|MANDATORY\s+SUBMISSIONS?)\b",
            re.IGNORECASE,
        ),
        [
            "required documents", "mandatory documents", "checklist of documents",
            "documents to be submitted", "list of documents", "checklist for bidders",
            "mandatory enclosures", "documents to upload",
        ],
        0.95,
    ),
    # 8. EMD (Earnest Money Deposit)
    (
        SectionType.EMD,
        "EMD",
        re.compile(
            r"^(?:(?:SECTION|PART|CHAPTER|CLAUSE|ANNEXURE)\s+[IVXLCDM\d\.]+\s*[:\-\.]?\s*)?"
            r"(?:EARNEST\s+MONEY\s+DEPOSIT|EMD(?:\s+DETAILS|\s+REQUIREMENTS?|\s+CLAUSE)?|"
            r"BID\s+SECURITY(?:\s+DECLARATION)?|EARNEST\s+MONEY)\b",
            re.IGNORECASE,
        ),
        [
            "earnest money deposit", "emd", "bid security", "emd exemption",
            "bid security declaration", "earnest money",
        ],
        0.95,
    ),
    # 9. Performance Security
    (
        SectionType.PERFORMANCE_SECURITY,
        "Performance Security",
        re.compile(
            r"^(?:(?:SECTION|PART|CHAPTER|CLAUSE|ANNEXURE)\s+[IVXLCDM\d\.]+\s*[:\-\.]?\s*)?"
            r"(?:PERFORMANCE\s+SECURITY|PERFORMANCE\s+BANK\s+GUARANTEE|PBG|"
            r"SECURITY\s+DEPOSIT|PERFORMANCE\s+GUARANTEE|CONTRACT\s+PERFORMANCE\s+SECURITY)\b",
            re.IGNORECASE,
        ),
        [
            "performance security", "performance bank guarantee", "pbg",
            "security deposit", "performance guarantee", "contract performance",
        ],
        0.95,
    ),
    # 10. Terms and Conditions
    (
        SectionType.TERMS_AND_CONDITIONS,
        "Terms and Conditions",
        re.compile(
            r"^(?:(?:SECTION|PART|CHAPTER|CLAUSE|ANNEXURE)\s+[IVXLCDM\d\.]+\s*[:\-\.]?\s*)?"
            r"(?:TERMS\s+AND\s+CONDITIONS|GENERAL\s+TERMS(?:\s+AND\s+CONDITIONS)?|"
            r"SPECIAL\s+TERMS(?:\s+AND\s+CONDITIONS)?|GENERAL\s+CONDITIONS\s+OF\s+CONTRACT|GCC|"
            r"SPECIAL\s+CONDITIONS\s+OF\s+CONTRACT|SCC|COMMERCIAL\s+TERMS|PAYMENT\s+TERMS)\b",
            re.IGNORECASE,
        ),
        [
            "terms and conditions", "general conditions of contract", "gcc",
            "special conditions of contract", "scc", "commercial terms",
            "payment terms", "general terms",
        ],
        0.90,
    ),
    # 11. Scope of Work
    (
        SectionType.SCOPE_OF_WORK,
        "Scope of Work",
        re.compile(
            r"^(?:(?:SECTION|PART|CHAPTER|CLAUSE|ANNEXURE)\s+[IVXLCDM\d\.]+\s*[:\-\.]?\s*)?"
            r"(?:SCOPE\s+OF\s+WORK|SCOPE\s+OF\s+SUPPLY|DETAILED\s+SCOPE(?:\s+OF\s+WORK)?|"
            r"WORK\s+DESCRIPTION|STATEMENT\s+OF\s+WORK|SOW|PROJECT\s+SCOPE)\b",
            re.IGNORECASE,
        ),
        [
            "scope of work", "scope of supply", "detailed scope",
            "statement of work", "sow", "work description", "project scope",
        ],
        0.95,
    ),
    # 12. Evaluation Criteria
    (
        SectionType.EVALUATION_CRITERIA,
        "Evaluation Criteria",
        re.compile(
            r"^(?:(?:SECTION|PART|CHAPTER|CLAUSE|ANNEXURE)\s+[IVXLCDM\d\.]+\s*[:\-\.]?\s*)?"
            r"(?:EVALUATION\s+CRITERIA|EVALUATION\s+METHODOLOGY|BID\s+EVALUATION|"
            r"SELECTION\s+CRITERIA|QCBS\s+EVALUATION|L1\s+EVALUATION(?:\s+PROCESS)?|"
            r"TECHNICAL\s+EVALUATION\s+MATRIX|METHOD\s+OF\s+EVALUATION)\b",
            re.IGNORECASE,
        ),
        [
            "evaluation criteria", "evaluation methodology", "bid evaluation",
            "selection criteria", "qcbs", "l1 evaluation", "evaluation matrix",
        ],
        0.95,
    ),
]

# Patterns that indicate a line is body text rather than a structural heading
BODY_SENTENCE_PREDICATES = re.compile(
    r"\b(?:must\s+(?:be|have|submit|furnish|produce|comply)|"
    r"shall\s+(?:be|have|submit|furnish|produce|not|remain)|"
    r"should\s+(?:be|have|submit)|"
    r"will\s+be|is\s+required\s+to|are\s+required\s+to|"
    r"applicable\s+after|per\s+week|at\s+least|not\s+less\s+than|"
    r"in\s+each\s+of|for\s+past\s+\d+|during\s+the\s+last)\b",
    re.IGNORECASE,
)


class TenderSectionDetector:
    """
    Deterministic Tender Section Detection Subsystem (Phase 11.6).
    Identifies and bounds common tender sections from normalized document representations,
    preserving exact page boundaries, section hierarchies, and structured entities.
    """

    def __init__(self, normalizer: Optional[DocumentContentNormalizer] = None):
        self.normalizer = normalizer or content_normalizer

    def is_valid_heading_line(self, line: str) -> bool:
        """
        Determines whether a line of text represents a structural heading vs body text.
        """
        if not line:
            return False

        clean = line.strip()
        # Headings are concise
        if len(clean) > 100:
            return False

        # If line contains affirmative sentence predicates, it is body text
        if BODY_SENTENCE_PREDICATES.search(clean):
            return False

        # Lines ending with a full stop with multiple words are typically sentences
        words = clean.split()
        if clean.endswith(".") and len(words) > 6:
            return False

        return True

    def classify_heading(self, heading_text: str, is_structural_heading: bool = False) -> Optional[Tuple[SectionType, str, float]]:
        """
        Classifies a candidate heading string into a canonical SectionType and name.
        Returns (SectionType, canonical_name, confidence) or None.
        """
        if not heading_text:
            return None

        clean_heading = self.normalizer.normalize_text(heading_text).strip()
        if not clean_heading or len(clean_heading) > 150:
            return None

        if not is_structural_heading and not self.is_valid_heading_line(clean_heading):
            return None

        # 1. Regex rule matching
        for s_type, s_name, pattern, _, conf in SECTION_DEFINITION_RULES:
            if pattern.search(clean_heading):
                return (s_type, s_name, conf)

        # 2. Substring / keyword matching (only if line is concise)
        if len(clean_heading.split()) <= 8:
            heading_lower = clean_heading.lower()
            for s_type, s_name, _, keywords, conf in SECTION_DEFINITION_RULES:
                for kw in keywords:
                    if kw in heading_lower:
                        return (s_type, s_name, conf * 0.90)

        return None

    def detect_sections_from_normalized(
        self,
        normalized_doc: NormalizedDocument,
    ) -> TenderSectionDetectionResult:
        """
        Extracts and bounds tender sections from a NormalizedDocument.
        """
        document_id = normalized_doc.document_id
        detected_sections: List[DetectedTenderSection] = []

        section_blocks: List[Dict[str, Any]] = []
        current_block: Optional[Dict[str, Any]] = None

        for p in normalized_doc.pages:
            page_num = p.page_number
            page_text = p.normalized_text or ""
            lines = [l.strip() for l in page_text.splitlines() if l.strip()]

            # 1. Check if page metadata already has an explicit section heading
            if p.section:
                classif = self.classify_heading(p.section, is_structural_heading=True)
                if classif:
                    s_type, s_name, conf = classif
                    if current_block is not None:
                        section_blocks.append(current_block)
                    current_block = {
                        "s_type": s_type,
                        "s_name": s_name,
                        "heading_raw": p.section,
                        "confidence": conf,
                        "page_start": page_num,
                        "page_end": page_num,
                        "text_parts": [],
                        "tables": list(p.tables),
                        "currencies": list(p.currencies),
                        "dates": list(p.dates),
                        "numbers": list(p.numbers),
                    }

            # 2. Inspect individual lines within the page
            for line in lines:
                classif = self.classify_heading(line, is_structural_heading=False)
                if classif:
                    s_type, s_name, conf = classif
                    if current_block is not None:
                        section_blocks.append(current_block)

                    current_block = {
                        "s_type": s_type,
                        "s_name": s_name,
                        "heading_raw": line,
                        "confidence": conf,
                        "page_start": page_num,
                        "page_end": page_num,
                        "text_parts": [],
                        "tables": [],
                        "currencies": [],
                        "dates": [],
                        "numbers": [],
                    }
                else:
                    if current_block is not None:
                        current_block["text_parts"].append(line)
                        current_block["page_end"] = max(current_block["page_end"], page_num)
                    else:
                        # Default starting block before any explicit heading is encountered
                        current_block = {
                            "s_type": SectionType.TENDER_INFORMATION,
                            "s_name": "Tender Information",
                            "heading_raw": "Tender Overview",
                            "confidence": 0.85,
                            "page_start": page_num,
                            "page_end": page_num,
                            "text_parts": [line],
                            "tables": [],
                            "currencies": [],
                            "dates": [],
                            "numbers": [],
                        }

        # Flush final block
        if current_block is not None:
            section_blocks.append(current_block)

        # Merge and build DetectedTenderSection instances
        for idx, blk in enumerate(section_blocks):
            sec_text = "\n".join(blk["text_parts"]).strip()
            # Extract structured items for this section text if not already present
            sec_currencies = self.normalizer.extract_currencies(sec_text)
            sec_dates = self.normalizer.extract_dates(sec_text)
            sec_numbers = self.normalizer.extract_numbers(sec_text)

            p_start = blk["page_start"]
            p_end = blk["page_end"]
            page_ref = f"Page {p_start}" if p_start == p_end else f"Pages {p_start}-{p_end}"
            src_ref = f"{page_ref} - {blk['heading_raw'] or blk['s_name']}"

            sec_id = f"sec-{idx + 1}-{blk['s_type'].value.lower().replace('_', '-')}"

            detected_sections.append(
                DetectedTenderSection(
                    section_id=sec_id,
                    name=blk["s_name"],
                    section_type=blk["s_type"],
                    heading_raw=blk["heading_raw"],
                    document_id=document_id,
                    page_start=p_start,
                    page_end=p_end,
                    source_reference=src_ref,
                    confidence=round(blk["confidence"], 2),
                    text=sec_text,
                    tables=blk["tables"],
                    currencies=sec_currencies,
                    dates=sec_dates,
                    numbers=sec_numbers,
                )
            )

        return TenderSectionDetectionResult(
            document_id=document_id,
            total_sections=len(detected_sections),
            sections=detected_sections,
            metadata={
                "page_count": normalized_doc.page_count,
                "format": normalized_doc.format,
            },
        )

    def detect_sections(
        self,
        extraction_result: ExtractionResult,
        document_id: Optional[str] = None,
    ) -> TenderSectionDetectionResult:
        """
        Convenience end-to-end method: normalizes an ExtractionResult and detects sections.
        """
        norm_doc = self.normalizer.normalize_document(
            extraction_result=extraction_result,
            document_id=document_id,
        )
        return self.detect_sections_from_normalized(norm_doc)


# Default singleton instance
tender_section_detector = TenderSectionDetector()
