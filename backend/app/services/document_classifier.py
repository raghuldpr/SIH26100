import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from app.models.enums import DocumentType
from app.schemas.classification import ClassificationResult

logger = logging.getLogger("app.services.document_classifier")


class RuleBasedDocumentClassifier:
    """
    Explainable, Rule-Based and Regex-Powered Document Classifier for SIH-26100.
    Classifies Indian procurement & vendor compliance documents:
    - PAN (Permanent Account Number)
    - GST (Goods and Services Tax Registration)
    - UDYAM (MSME Registration Certificate)
    - FINANCIAL_STATEMENT (Balance Sheets, Audited P&L, Turnover Certificates)
    - EXPERIENCE_CERTIFICATE (Work Orders, Completion Certificates)
    - OEM_AUTHORIZATION (Manufacturer Authorization Form / MAF)
    - MII_DECLARATION (Make in India / Local Content Declarations)
    - TENDER (RFP, Notice Inviting Tender, Bid Scope)
    - OTHER (Unmatched, generic, or ambiguous documents)
    """

    def __init__(self, min_confidence_threshold: float = 0.50):
        self.min_confidence_threshold = min_confidence_threshold

        # Define Rule Bases: (Primary Regexes, Primary Phrases, Secondary Keywords, Filename Clues)
        self.rules: Dict[str, Dict[str, Any]] = {
            "PAN": {
                "regexes": [
                    (r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", "PAN regex pattern [XXXXX9999X]", 5.0),
                ],
                "primary_phrases": [
                    ("permanent account number", 4.0),
                    ("income tax department", 4.0),
                    ("incometax department", 4.0),
                    ("father's name", 3.0),
                    ("date of birth", 2.5),
                    ("govt. of india", 2.0),
                    ("government of india", 2.0),
                ],
                "secondary_keywords": [
                    ("pan card", 2.0),
                    ("form 49a", 2.0),
                    ("taxpayer identification", 2.0),
                ],
                "filename_keywords": ["pan", "pancard", "pan_card"],
            },
            "GST": {
                "regexes": [
                    (r"\b\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1}\b", "GSTIN regex pattern [22XXXXX9999X1ZX]", 6.0),
                    (r"\bFORM\s+GST\s+REG-\d+\b", "Form GST REG form identifier", 4.0),
                ],
                "primary_phrases": [
                    ("goods and services tax", 4.0),
                    ("gstin", 4.0),
                    ("registration certificate", 3.0),
                    ("principal place of business", 3.0),
                    ("date of liability", 3.0),
                    ("taxpayer type", 2.5),
                ],
                "secondary_keywords": [
                    ("central tax", 1.5),
                    ("state tax", 1.5),
                    ("jurisdiction", 1.5),
                    ("gst council", 1.5),
                ],
                "filename_keywords": ["gst", "gstin", "gst_cert", "gst_certificate", "gst_registration"],
            },
            "UDYAM": {
                "regexes": [
                    (r"\bUDYAM-[A-Z]{2}-\d{2}-\d{7}\b", "Udyam Registration Number format [UDYAM-XX-00-0000000]", 6.0),
                ],
                "primary_phrases": [
                    ("udyam registration certificate", 5.0),
                    ("ministry of micro, small and medium enterprises", 4.5),
                    ("micro, small and medium enterprises", 3.5),
                    ("enterprise type", 3.0),
                    ("major activity", 3.0),
                    ("national industry classification", 3.0),
                    ("msme", 2.5),
                ],
                "secondary_keywords": [
                    ("udyam", 2.0),
                    ("micro enterprise", 2.0),
                    ("small enterprise", 2.0),
                    ("medium enterprise", 2.0),
                    ("nic code", 1.5),
                    ("dic", 1.5),
                ],
                "filename_keywords": ["udyam", "msme", "udyam_cert", "udyam_registration"],
            },
            "FINANCIAL_STATEMENT": {
                "regexes": [
                    (r"\bUDIN\s*[:\s]*[A-Za-z0-9]{18}\b", "ICAI Unique Document Identification Number (UDIN)", 5.0),
                ],

                "primary_phrases": [
                    ("balance sheet", 4.5),
                    ("statement of profit and loss", 4.5),
                    ("profit and loss statement", 4.5),
                    ("profit & loss", 4.0),
                    ("independent auditor's report", 4.5),
                    ("auditor's report", 4.0),
                    ("chartered accountant", 3.5),
                    ("cash flow statement", 3.5),
                    ("annual turnover", 3.0),
                    ("net worth certificate", 3.5),
                ],
                "secondary_keywords": [
                    ("equity and liabilities", 2.0),
                    ("current assets", 2.0),
                    ("revenue from operations", 2.0),
                    ("depreciation and amortization", 2.0),
                    ("turnover certificate", 3.0),
                    ("ca membership no", 2.5),
                ],
                "filename_keywords": ["balance_sheet", "pnl", "financial", "turnover", "audit", "audited_financials"],
            },
            "EXPERIENCE_CERTIFICATE": {
                "regexes": [],
                "primary_phrases": [
                    ("experience certificate", 5.0),
                    ("work completion certificate", 5.0),
                    ("completion certificate", 4.5),
                    ("work order", 4.0),
                    ("satisfactory completion", 4.0),
                    ("satisfactory performance", 4.0),
                    ("purchase order", 3.5),
                    ("performance certificate", 4.0),
                    ("scope of work completed", 3.5),
                    ("client certificate", 3.5),
                ],
                "secondary_keywords": [
                    ("satisfactorily executed", 2.5),
                    ("contract value", 2.0),
                    ("execution of work", 2.0),
                    ("work experience", 2.5),
                    ("letter of award", 3.0),
                ],
                "filename_keywords": ["experience", "completion", "work_order", "po", "client_cert", "past_experience"],
            },
            "OEM_AUTHORIZATION": {
                "regexes": [
                    (r"\bMAF\b", "Manufacturer Authorization Form abbreviation", 2.0),
                ],
                "primary_phrases": [
                    ("manufacturer's authorization form", 5.0),
                    ("manufacturers authorization", 5.0),
                    ("manufacturer authorization", 5.0),
                    ("oem authorization", 5.0),
                    ("original equipment manufacturer", 4.0),
                    ("authorized partner", 3.5),
                    ("authorized distributor", 3.5),
                    ("authorized reseller", 3.5),
                    ("we hereby authorize", 4.0),
                    ("authorization letter", 3.5),
                ],
                "secondary_keywords": [
                    ("authorized channel partner", 2.5),
                    ("oem certificate", 3.0),
                    ("valid for bid", 2.0),
                    ("sole authorized", 2.5),
                ],
                "filename_keywords": ["oem", "maf", "authorization", "oem_auth", "auth_letter"],
            },
            "MII_DECLARATION": {
                "regexes": [],
                "primary_phrases": [
                    ("make in india", 4.5),
                    ("mii declaration", 5.0),
                    ("class-i local supplier", 5.0),
                    ("class-ii local supplier", 5.0),
                    ("local content percentage", 4.5),
                    ("public procurement (preference to make in india)", 4.5),
                    ("local content declaration", 4.5),
                    ("certificate of local content", 4.5),
                    ("local value addition", 3.5),
                ],
                "secondary_keywords": [
                    ("ppp-mii", 3.0),
                    ("indigenous content", 2.5),
                    ("self-declaration for local content", 4.0),
                    ("percentage of local content", 3.5),
                ],
                "filename_keywords": ["mii", "make_in_india", "local_content", "mii_declaration"],
            },
            "TENDER": {
                "regexes": [
                    (r"\bNIT\s*NO[.:\s]*", "Notice Inviting Tender Identifier", 4.0),
                    (r"\bGEM/\d{4}/[A-Z]/\d+\b", "GeM Bid Number format [GEM/2026/B/123456]", 5.0),
                ],
                "primary_phrases": [
                    ("notice inviting tender", 5.0),
                    ("request for proposal", 5.0),
                    ("tender document", 4.5),
                    ("tender notice", 4.5),
                    ("bid document", 4.0),
                    ("tender inviting authority", 4.0),
                    ("bid submission deadline", 3.5),
                    ("earnest money deposit", 3.5),
                    ("emd", 2.5),
                    ("two bid system", 3.0),
                    ("scope of supply", 3.5),
                    ("eligibility criteria", 2.5),
                ],
                "secondary_keywords": [
                    ("tender no", 2.5),
                    ("bid end date", 2.5),
                    ("technical bid", 2.5),
                    ("financial bid", 2.5),
                    ("procuring entity", 2.0),
                    ("terms and conditions of tender", 3.0),
                ],
                "filename_keywords": ["tender", "rfp", "nit", "bid_doc", "scope_of_work", "tender_notice"],
            },
        }

    def classify(
        self,
        text: Optional[str] = None,
        filename: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ClassificationResult:
        """
        Evaluates document text, regex patterns, and optional filename signals
        to return an explainable classification result.
        """
        raw_text = (text or "").lower()
        clean_text_orig = text or ""
        fn = (filename or "").lower()

        scores: Dict[str, float] = {k: 0.0 for k in self.rules}
        matched_signals_map: Dict[str, List[str]] = {k: [] for k in self.rules}

        # 1. Evaluate Rule Match per Category
        for doc_type, rule_set in self.rules.items():
            # A. Regex checks (applied on original case text for accurate uppercase codes)
            for pattern, desc, weight in rule_set.get("regexes", []):
                matches = re.findall(pattern, clean_text_orig, re.IGNORECASE)
                if matches:
                    scores[doc_type] += weight
                    matched_signals_map[doc_type].append(f"Regex: {desc} (matches: {len(matches)})")

            # B. Primary multi-word phrase checks
            for phrase, weight in rule_set.get("primary_phrases", []):
                if phrase.lower() in raw_text:
                    scores[doc_type] += weight
                    matched_signals_map[doc_type].append(f"Phrase: '{phrase.title()}'")

            # C. Secondary keywords
            for kw, weight in rule_set.get("secondary_keywords", []):
                if kw.lower() in raw_text:
                    scores[doc_type] += weight
                    matched_signals_map[doc_type].append(f"Keyword: '{kw.title()}'")

            # D. Filename hint (provides a moderate boost, never overrides strong text)
            for fn_kw in rule_set.get("filename_keywords", []):
                # Match word boundary or separator in filename
                if re.search(rf"(?:^|[_\-\.\s]){re.escape(fn_kw)}(?:[_\-\.\s]|$)", fn):
                    scores[doc_type] += 1.5
                    matched_signals_map[doc_type].append(f"Filename signal: '{fn_kw}'")
                    break  # count only once per category


        # 2. Determine Best Match
        sorted_candidates = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        best_doc_type, highest_score = sorted_candidates[0]
        second_best_score = sorted_candidates[1][1] if len(sorted_candidates) > 1 else 0.0

        # 3. Calculate Normalized Confidence Score
        # Max expected score is roughly 10.0-15.0 for strong matches
        if highest_score <= 0.0 or len(matched_signals_map[best_doc_type]) == 0:
            return ClassificationResult(
                document_type=DocumentType.OTHER.value,
                confidence=0.10,
                matched_signals=[],
                explanation="No distinctive document indicators or compliance signatures detected.",
                scores=scores,
            )

        # Non-linear confidence mapping:
        # Score >= 6.0 -> 0.90 to 0.99
        # Score 4.0-6.0 -> 0.80 to 0.89
        # Score 2.0-4.0 -> 0.60 to 0.79
        # Score < 2.0 -> classified as OTHER if below threshold
        if highest_score >= 8.0:
            calculated_conf = min(0.99, 0.90 + (highest_score - 8.0) * 0.02)
        elif highest_score >= 5.0:
            calculated_conf = 0.80 + (highest_score - 5.0) * 0.03
        elif highest_score >= 3.0:
            calculated_conf = 0.65 + (highest_score - 3.0) * 0.075
        else:
            calculated_conf = 0.40 + (highest_score / 3.0) * 0.20

        # Margin boost: If best score significantly exceeds runner-up, boost confidence
        if (highest_score - second_best_score) >= 3.0:
            calculated_conf = min(0.99, calculated_conf + 0.05)

        calculated_conf = float(round(calculated_conf, 2))

        # Check if score meets minimum confidence threshold
        if calculated_conf < self.min_confidence_threshold or highest_score < 2.0:
            return ClassificationResult(
                document_type=DocumentType.OTHER.value,
                confidence=float(round(max(0.10, calculated_conf), 2)),
                matched_signals=matched_signals_map[best_doc_type],
                explanation=f"Signals for '{best_doc_type}' were below the required certainty threshold ({calculated_conf} < {self.min_confidence_threshold}).",
                scores=scores,
            )

        explanation = (
            f"Classified as '{best_doc_type}' with score {highest_score:.1f} "
            f"based on {len(matched_signals_map[best_doc_type])} matching indicator(s)."
        )

        return ClassificationResult(
            document_type=best_doc_type,
            confidence=calculated_conf,
            matched_signals=matched_signals_map[best_doc_type],
            explanation=explanation,
            scores=scores,
        )


# Default singleton instance
document_classifier = RuleBasedDocumentClassifier()
