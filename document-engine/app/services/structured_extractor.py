import logging
import re
from typing import Any, Dict, Optional, Tuple

from app.classifiers.document_classifier import DocumentClassifier
from app.schemas.structured import StructuredExtractionResult

logger = logging.getLogger("document_engine.structured_extractor")

# Compiled Common Regex Patterns
PAN_PATTERN = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b")
GSTIN_PATTERN = re.compile(r"\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}\b")
UDYAM_PATTERN = re.compile(r"\bUDYAM-[A-Z]{2}-[0-9]{2}-[0-9]{7}\b", re.IGNORECASE)
GEM_BID_PATTERN = re.compile(r"\bGEM/[0-9]{4}/[A-Z]/[0-9]+\b", re.IGNORECASE)
DATE_PATTERN = re.compile(
    r"\b([0-9]{1,2}[-/\.][0-9]{1,2}[-/\.][0-9]{2,4}|[0-9]{1,2}\s+[A-Za-z]{3,9}\s+[0-9]{4})\b"
)


class StructuredExtractor:
    """
    Deterministic structured field extraction using regex, normalization, and keyword proximity.
    Does not verify authenticity or invent missing data; missing fields return None.
    """

    @classmethod
    def clean_text(cls, val: Optional[str]) -> Optional[str]:
        """Cleans extracted raw field strings, collapses spacing, and removes edge punctuation."""
        if val is None:
            return None
        text = re.sub(r"\s+", " ", val).strip(" \t\r\n:;-, '\"")
        if text.endswith(".") and not re.search(r"\b(ltd|pvt|inc|corp|co)\.$", text, re.IGNORECASE):
            text = text[:-1].strip()
        return text if text else None

    # =========================================================================
    # 1. GST EXTRACTION
    # =========================================================================
    @classmethod
    def extract_gst(cls, text: str) -> Tuple[Dict[str, Any], Dict[str, float]]:
        data: Dict[str, Any] = {
            "gstin": None,
            "company_name": None,
            "legal_name": None,
            "status": None,
        }
        confidence: Dict[str, float] = {}

        # GSTIN (Regex pattern)
        gstin_match = GSTIN_PATTERN.search(text)
        if gstin_match:
            data["gstin"] = gstin_match.group(0).upper()
            confidence["gstin"] = 0.99

        # Legal Name
        legal_match = re.search(
            r"(?:Legal\s*Name(?:\s*of\s*the\s*Taxpayer)?|Name\s*of\s*the\s*Taxpayer)\s*[:\-]\s*([^\n\r]+)",
            text,
            re.IGNORECASE,
        )
        if legal_match:
            cleaned = cls.clean_text(legal_match.group(1))
            if cleaned:
                data["legal_name"] = cleaned
                confidence["legal_name"] = 0.93

        # Company / Trade Name
        trade_match = re.search(
            r"(?:Trade\s*Name|Business\s*Name)\s*[:\-]\s*([^\n\r]+)",
            text,
            re.IGNORECASE,
        )
        if trade_match:
            cleaned = cls.clean_text(trade_match.group(1))
            if cleaned:
                data["company_name"] = cleaned
                confidence["company_name"] = 0.91
        elif data["legal_name"]:
            # Fallback company name to legal name with lower confidence if not distinct
            data["company_name"] = data["legal_name"]
            confidence["company_name"] = 0.75

        # Status
        status_match = re.search(
            r"(?:Status|Registration\s*Status)\s*[:\-]\s*([A-Za-z]+)",
            text,
            re.IGNORECASE,
        )
        if status_match:
            data["status"] = status_match.group(1).title()
            confidence["status"] = 0.90
        elif "registration certificate" in text.lower() and data["gstin"]:
            data["status"] = "Active"
            confidence["status"] = 0.85

        return data, confidence

    # =========================================================================
    # 2. PAN EXTRACTION
    # =========================================================================
    @classmethod
    def extract_pan(cls, text: str) -> Tuple[Dict[str, Any], Dict[str, float]]:
        data: Dict[str, Any] = {
            "pan": None,
            "name": None,
        }
        confidence: Dict[str, float] = {}

        # PAN Number
        pan_match = PAN_PATTERN.search(text)
        if pan_match:
            data["pan"] = pan_match.group(0).upper()
            confidence["pan"] = 0.99

        # Cardholder Name
        name_match = re.search(
            r"^[ \t]*(?<!Father's\s)(?<!Father\s)(?:Name|Cardholder(?:'s)?\s*Name)\s*[:\-]\s*([^\n\r]+)",
            text,
            re.IGNORECASE | re.MULTILINE,
        )
        if name_match:
            cleaned = cls.clean_text(name_match.group(1))
            if cleaned and len(cleaned) > 2:
                data["name"] = cleaned.upper()
                confidence["name"] = 0.92
        else:
            # Look for lines between Department title and Father's Name
            lines = [cls.clean_text(l) for l in text.splitlines() if cls.clean_text(l)]
            for i, line in enumerate(lines):
                if re.search(r"father(?:'s)?\s*name", line, re.IGNORECASE) and i > 0:
                    candidate = lines[i - 1]
                    if candidate and not PAN_PATTERN.search(candidate) and len(candidate.split()) <= 4:
                        data["name"] = candidate.upper()
                        confidence["name"] = 0.78
                        break

        return data, confidence

    # =========================================================================
    # 3. UDYAM EXTRACTION
    # =========================================================================
    @classmethod
    def extract_udyam(cls, text: str) -> Tuple[Dict[str, Any], Dict[str, float]]:
        data: Dict[str, Any] = {
            "udyam_number": None,
            "enterprise_name": None,
            "enterprise_type": None,
        }
        confidence: Dict[str, float] = {}

        # Udyam Number
        udyam_match = UDYAM_PATTERN.search(text)
        if udyam_match:
            data["udyam_number"] = udyam_match.group(0).upper()
            confidence["udyam_number"] = 0.99

        # Enterprise Name
        name_match = re.search(
            r"(?:NAME\s*OF\s*ENTERPRISE|ENTERPRISE\s*NAME)\s*[:\-]\s*([^\n\r]+)",
            text,
            re.IGNORECASE,
        )
        if name_match:
            cleaned = cls.clean_text(name_match.group(1))
            if cleaned:
                data["enterprise_name"] = cleaned
                confidence["enterprise_name"] = 0.92

        # Enterprise Type (Micro, Small, Medium)
        type_match = re.search(
            r"(?:TYPE\s*OF\s*ENTERPRISE|ENTERPRISE\s*TYPE)\s*[:\-]?\s*(MICRO|SMALL|MEDIUM)",
            text,
            re.IGNORECASE,
        )
        if type_match:
            data["enterprise_type"] = type_match.group(1).upper()
            confidence["enterprise_type"] = 0.95
        else:
            # Keyword search for Micro / Small / Medium
            for etype in ["MICRO", "SMALL", "MEDIUM"]:
                if re.search(rf"\b{etype}\s*ENTERPRISE\b", text, re.IGNORECASE):
                    data["enterprise_type"] = etype
                    confidence["enterprise_type"] = 0.85
                    break

        return data, confidence

    # =========================================================================
    # 4. FINANCIAL_STATEMENT EXTRACTION
    # =========================================================================
    @classmethod
    def extract_financial_statement(cls, text: str) -> Tuple[Dict[str, Any], Dict[str, float]]:
        data: Dict[str, Any] = {
            "company_name": None,
            "financial_year": None,
            "revenue": None,
            "profit": None,
            "statement_type": None,
        }
        confidence: Dict[str, float] = {}

        # Company Name
        company_match = re.search(
            r"(?:To\s*the\s*Members\s*of|Balance\s*Sheet\s*of|Auditor(?:'s)?\s*Report\s*on)\s*[:\-]?\s*([^\n\r,]+)",
            text,
            re.IGNORECASE,
        )
        if company_match:
            cleaned = cls.clean_text(company_match.group(1))
            if cleaned:
                data["company_name"] = cleaned
                confidence["company_name"] = 0.88

        # Financial Year - prioritize explicit range like 2024-25 or FY: 2024-25
        fy_range_match = re.search(
            r"(?:FY|Financial\s*Year)?\s*[:\-]?\s*([0-9]{4}[-\u2013][0-9]{2,4})",
            text,
            re.IGNORECASE,
        )
        if fy_range_match:
            data["financial_year"] = fy_range_match.group(1).replace("\u2013", "-")
            confidence["financial_year"] = 0.95
        else:
            # Check for year ended March 31, YYYY or 31st March YYYY
            march_match = re.search(
                r"(?:31st\s*March|year\s*ended\s*(?:March\s*31,?\s*)?)\s*([0-9]{4})",
                text,
                re.IGNORECASE,
            )
            if march_match:
                yr = int(march_match.group(1))
                data["financial_year"] = f"{yr-1}-{str(yr)[-2:]}"
                confidence["financial_year"] = 0.80

        # Revenue / Turnover
        rev_match = re.search(
            r"(?:Annual\s*Turnover|Turnover|Revenue\s*from\s*Operations)\s*[:\-]?\s*(?:INR|Rs\.?|₹)?\s*([0-9,]+(?:\.[0-9]{2})?)",
            text,
            re.IGNORECASE,
        )
        if rev_match:
            raw_rev = rev_match.group(1).replace(",", "")
            try:
                data["revenue"] = float(raw_rev) if "." in raw_rev else int(raw_rev)
                confidence["revenue"] = 0.88
            except ValueError:
                data["revenue"] = rev_match.group(1)
                confidence["revenue"] = 0.70

        # Profit
        profit_match = re.search(
            r"(?:Net\s*Profit|Profit\s*(?:after\s*Tax|for\s*the\s*year)|PAT)\s*[:\-]?\s*(?:INR|Rs\.?|₹)?\s*([0-9,]+(?:\.[0-9]{2})?)",
            text,
            re.IGNORECASE,
        )
        if profit_match:
            raw_profit = profit_match.group(1).replace(",", "")
            try:
                data["profit"] = float(raw_profit) if "." in raw_profit else int(raw_profit)
                confidence["profit"] = 0.88
            except ValueError:
                data["profit"] = profit_match.group(1)
                confidence["profit"] = 0.70

        # Statement Type
        if "balance sheet" in text.lower():
            data["statement_type"] = "Balance Sheet"
            confidence["statement_type"] = 0.95
        elif "profit and loss" in text.lower():
            data["statement_type"] = "Profit and Loss"
            confidence["statement_type"] = 0.95
        elif "auditor" in text.lower():
            data["statement_type"] = "Audited Financials"
            confidence["statement_type"] = 0.85

        return data, confidence

    # =========================================================================
    # 5. EXPERIENCE_CERTIFICATE EXTRACTION
    # =========================================================================
    @classmethod
    def extract_experience_certificate(cls, text: str) -> Tuple[Dict[str, Any], Dict[str, float]]:
        data: Dict[str, Any] = {
            "company_name": None,
            "client_name": None,
            "project_name": None,
            "project_value": None,
            "completion_date": None,
        }
        confidence: Dict[str, float] = {}

        # Company (Contractor) Name
        comp_match = re.search(
            r"(?:certify\s*that\s*(?:M/s\.?|M/S)?|awarded\s*to\s*(?:M/s\.?|M/S)?)\s*([^\n\r,]+?)(?:\s+has|\s+have|\s*,\s*|$)",
            text,
            re.IGNORECASE,
        )
        if comp_match:
            cleaned = cls.clean_text(comp_match.group(1))
            if cleaned:
                data["company_name"] = cleaned
                confidence["company_name"] = 0.90

        # Client / Issuing Authority Name
        client_match = re.search(
            r"(?:Issued\s*by|Client(?:\s*Name)?|Organization)\s*[:\-]\s*([^\n\r]+)",
            text,
            re.IGNORECASE,
        )
        if client_match:
            cleaned = cls.clean_text(client_match.group(1))
            if cleaned:
                data["client_name"] = cleaned
                confidence["client_name"] = 0.88

        # Project Name / Scope
        proj_match = re.search(
            r"(?:execution\s*of\s*work\s*for|project\s*name\s*[:\-]|work\s*of)\s*['\"]?([^'\"\n\r]+)['\"]?",
            text,
            re.IGNORECASE,
        )
        if proj_match:
            cleaned = cls.clean_text(proj_match.group(1))
            if cleaned:
                data["project_name"] = cleaned
                confidence["project_name"] = 0.86

        # Project Value
        val_match = re.search(
            r"(?:Contract\s*Value|Work\s*Order\s*Value|Executed\s*Value|Value)\s*[:\-]?\s*(?:Rs\.?|INR|₹)?\s*([0-9,]+(?:\.[0-9]{2})?)",
            text,
            re.IGNORECASE,
        )
        if val_match:
            raw_val = val_match.group(1).replace(",", "")
            try:
                data["project_value"] = float(raw_val) if "." in raw_val else int(raw_val)
                confidence["project_value"] = 0.90
            except ValueError:
                data["project_value"] = val_match.group(1)
                confidence["project_value"] = 0.70

        # Completion Date
        date_match = re.search(
            r"(?:Date\s*of\s*Completion|Completion\s*Date|Completed\s*on)\s*[:\-]?\s*([0-9]{1,2}[-/\.][A-Za-z0-9]{2,4}[-/\.][0-9]{2,4}|[0-9]{1,2}\s+[A-Za-z]{3,9}\s+[0-9]{4})",
            text,
            re.IGNORECASE,
        )
        if date_match:
            data["completion_date"] = date_match.group(1)
            confidence["completion_date"] = 0.92

        return data, confidence

    # =========================================================================
    # 6. OEM_AUTHORIZATION EXTRACTION
    # =========================================================================
    @classmethod
    def extract_oem_authorization(cls, text: str) -> Tuple[Dict[str, Any], Dict[str, float]]:
        data: Dict[str, Any] = {
            "oem_name": None,
            "authorized_bidder": None,
            "authorization_date": None,
            "product": None,
        }
        confidence: Dict[str, float] = {}

        # OEM (Manufacturer) Name
        oem_match = re.search(
            r"(?:We,\s*|Manufacturer\s*[:\-]\s*)([^\n\r,]+?)(?:,\s*who\s*are\s*official|\s*hereby\s*authorize)",
            text,
            re.IGNORECASE,
        )
        if oem_match:
            cleaned = cls.clean_text(oem_match.group(1))
            if cleaned:
                data["oem_name"] = cleaned
                confidence["oem_name"] = 0.92

        # Authorized Bidder
        bidder_match = re.search(
            r"(?:hereby\s*authorize|authorized\s*partner\s*is)\s*([^\n\r,]+?)(?:\s+to\s+submit|\s+to\s+bid|\s+as|\s*,\s*|$)",
            text,
            re.IGNORECASE,
        )
        if bidder_match:
            cleaned = cls.clean_text(bidder_match.group(1))
            if cleaned:
                data["authorized_bidder"] = cleaned
                confidence["authorized_bidder"] = 0.90

        # Authorization Date
        date_match = re.search(
            r"(?:Date|Dated)\s*[:\-]\s*([0-9]{1,2}[-/\.][A-Za-z0-9]{2,4}[-/\.][0-9]{2,4}|[0-9]{1,2}\s+[A-Za-z]{3,9}\s+[0-9]{4})",
            text,
            re.IGNORECASE,
        )
        if date_match:
            data["authorization_date"] = date_match.group(1)
            confidence["authorization_date"] = 0.88

        # Product / Category
        prod_match = re.search(
            r"(?:official\s*manufacturer\s*of|supply\s*of|products?\s*[:\-])\s*['\"]?([^'\"\n\r,]+)['\"]?",
            text,
            re.IGNORECASE,
        )
        if prod_match:
            cleaned = cls.clean_text(prod_match.group(1))
            if cleaned:
                data["product"] = cleaned
                confidence["product"] = 0.85

        return data, confidence

    # =========================================================================
    # 7. MII_DECLARATION EXTRACTION
    # =========================================================================
    @classmethod
    def extract_mii_declaration(cls, text: str) -> Tuple[Dict[str, Any], Dict[str, float]]:
        data: Dict[str, Any] = {
            "bidder_name": None,
            "local_content_percentage": None,
            "country_of_origin": None,
            "declaration_date": None,
        }
        confidence: Dict[str, float] = {}

        # Bidder Name
        bidder_match = re.search(
            r"(?:certify\s*that\s*(?:M/s\.?|M/S)?|Bidder(?:\s*Name)?\s*[:\-])\s*([^\n\r,]+?)(?:\s+is|\s+has|\s+have|\s*,\s*|$)",
            text,
            re.IGNORECASE,
        )
        if bidder_match:
            cleaned = cls.clean_text(bidder_match.group(1))
            if cleaned:
                data["bidder_name"] = cleaned
                confidence["bidder_name"] = 0.88

        # Local Content Percentage
        pct_match = re.search(
            r"(?:local\s*content(?:\s*percentage)?|percentage\s*of\s*local\s*content)\s*[:\-]?\s*([0-9]+(?:\.[0-9]+)?)\s*%",
            text,
            re.IGNORECASE,
        )
        if pct_match:
            try:
                data["local_content_percentage"] = float(pct_match.group(1))
                confidence["local_content_percentage"] = 0.95
            except ValueError:
                data["local_content_percentage"] = pct_match.group(1)
                confidence["local_content_percentage"] = 0.70

        # Country of Origin
        country_match = re.search(
            r"(?:Country\s*of\s*Origin)\s*[:\-]\s*([^\n\r]+)",
            text,
            re.IGNORECASE,
        )
        if country_match:
            cleaned = cls.clean_text(country_match.group(1))
            if cleaned:
                data["country_of_origin"] = cleaned
                confidence["country_of_origin"] = 0.92

        # Declaration Date
        date_match = re.search(
            r"(?:Date|Dated)\s*[:\-]\s*([0-9]{1,2}[-/\.][A-Za-z0-9]{2,4}[-/\.][0-9]{2,4}|[0-9]{1,2}\s+[A-Za-z]{3,9}\s+[0-9]{4})",
            text,
            re.IGNORECASE,
        )
        if date_match:
            data["declaration_date"] = date_match.group(1)
            confidence["declaration_date"] = 0.88

        return data, confidence

    # =========================================================================
    # 8. TENDER EXTRACTION
    # =========================================================================
    @classmethod
    def extract_tender(cls, text: str) -> Tuple[Dict[str, Any], Dict[str, float]]:
        data: Dict[str, Any] = {
            "tender_reference": None,
            "issuing_organization": None,
            "title": None,
            "bid_deadline": None,
            "estimated_value": None,
        }
        confidence: Dict[str, float] = {}

        # Tender Reference
        gem_match = GEM_BID_PATTERN.search(text)
        if gem_match:
            data["tender_reference"] = gem_match.group(0).upper()
            confidence["tender_reference"] = 0.99
        else:
            ref_match = re.search(
                r"(?:Bid\s*Number|Tender\s*(?:Ref|Reference|Notice\s*No)?)\s*[:\-]\s*([A-Za-z0-9/\-_]+)",
                text,
                re.IGNORECASE,
            )
            if ref_match:
                data["tender_reference"] = ref_match.group(1)
                confidence["tender_reference"] = 0.90

        # Issuing Organization
        org_match = re.search(
            r"(?:Ministry/State\s*Name|Buyer\s*Organization|Department)\s*[:\-]\s*([^\n\r,]+)",
            text,
            re.IGNORECASE,
        )
        if org_match:
            cleaned = cls.clean_text(org_match.group(1))
            if cleaned:
                data["issuing_organization"] = cleaned
                confidence["issuing_organization"] = 0.88

        # Title
        title_match = re.search(
            r"(?:Notice\s*Inviting\s*Tender\s*for|Procurement\s*of|Item\s*Category)\s*[:\-]?\s*([^\n\r]+)",
            text,
            re.IGNORECASE,
        )
        if title_match:
            cleaned = cls.clean_text(title_match.group(1))
            if cleaned:
                data["title"] = cleaned
                confidence["title"] = 0.85

        # Bid Deadline
        deadline_match = re.search(
            r"(?:Bid\s*End\s*Date\s*(?:/\s*Time)?|Submission\s*Deadline|Due\s*Date)\s*[:\-]\s*([0-9]{1,2}[-/\.][A-Za-z0-9]{2,4}[-/\.][0-9]{2,4}(?:\s+[0-9]{1,2}:[0-9]{2}(?::[0-9]{2})?)?)",
            text,
            re.IGNORECASE,
        )
        if deadline_match:
            data["bid_deadline"] = deadline_match.group(1)
            confidence["bid_deadline"] = 0.92

        # Estimated Value
        val_match = re.search(
            r"(?:Estimated\s*(?:Bid)?\s*Value|Total\s*Value|Tender\s*Value)\s*[:\-]?\s*(?:INR|Rs\.?|₹)?\s*([0-9,]+(?:\.[0-9]{2})?)",
            text,
            re.IGNORECASE,
        )
        if val_match:
            raw_val = val_match.group(1).replace(",", "")
            try:
                data["estimated_value"] = float(raw_val) if "." in raw_val else int(raw_val)
                confidence["estimated_value"] = 0.88
            except ValueError:
                data["estimated_value"] = val_match.group(1)
                confidence["estimated_value"] = 0.70

        return data, confidence

    # =========================================================================
    # ORCHESTRATOR
    # =========================================================================
    @classmethod
    def extract_structured_data(
        cls, text: str, doc_type: Optional[str] = None
    ) -> StructuredExtractionResult:
        """
        Dispatches text extraction to the appropriate document type extractor.
        If doc_type is omitted or UNKNOWN, classifies text first.
        """
        target_type = doc_type
        if not target_type or target_type.upper() == "UNKNOWN":
            classification = DocumentClassifier.classify_text(text)
            target_type = classification.document_type

        target_type = target_type.upper()

        if target_type == "GST":
            data, conf = cls.extract_gst(text)
        elif target_type == "PAN":
            data, conf = cls.extract_pan(text)
        elif target_type == "UDYAM":
            data, conf = cls.extract_udyam(text)
        elif target_type == "FINANCIAL_STATEMENT":
            data, conf = cls.extract_financial_statement(text)
        elif target_type == "EXPERIENCE_CERTIFICATE":
            data, conf = cls.extract_experience_certificate(text)
        elif target_type == "OEM_AUTHORIZATION":
            data, conf = cls.extract_oem_authorization(text)
        elif target_type == "MII_DECLARATION":
            data, conf = cls.extract_mii_declaration(text)
        elif target_type == "TENDER":
            data, conf = cls.extract_tender(text)
        else:
            return StructuredExtractionResult(
                document_type="UNKNOWN",
                data={},
                field_confidence={},
            )

        return StructuredExtractionResult(
            document_type=target_type,
            data=data,
            field_confidence=conf,
        )


def extract_structured_data(
    text: str, doc_type: Optional[str] = None
) -> StructuredExtractionResult:
    """Convenience helper for structured field extraction."""
    return StructuredExtractor.extract_structured_data(text, doc_type=doc_type)
