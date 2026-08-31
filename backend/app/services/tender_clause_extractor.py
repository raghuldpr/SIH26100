import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple, Union

from app.models.enums import RequirementType
from app.schemas.tender_clause import ClauseCandidate, ClauseExtractionResult

logger = logging.getLogger("app.services.tender_clause_extractor")


class TenderClauseExtractor:
    """
    Deterministic clause extraction subsystem for Tender Intelligence (Phase 08).
    Extracts candidate eligibility and compliance clauses with section awareness,
    prescriptive marker validation, and full audit explainability.
    """

    # -------------------------------------------------------------------------
    # 1. SECTION HEADING DETECTION PATTERNS
    # -------------------------------------------------------------------------
    SECTION_PATTERNS = [
        (
            re.compile(
                r"^(?:(?:SECTION|PART|CHAPTER|CLAUSE)\s+[IVXLCDM\d\.]+\s*[:\-\.]?\s*)?"
                r"(ELIGIBILITY(?:\s+CRITERIA|\s+CONDITIONS)?|MINIMUM\s+ELIGIBILITY|"
                r"QUALIFICATION(?:\s+CRITERIA|\s+REQUIREMENTS?)?|PRE-QUALIFICATION\s+CRITERIA)\b",
                re.IGNORECASE,
            ),
            "Eligibility Criteria",
        ),
        (
            re.compile(
                r"^(?:(?:SECTION|PART|CHAPTER|CLAUSE)\s+[IVXLCDM\d\.]+\s*[:\-\.]?\s*)?"
                r"(FINANCIAL(?:\s+CRITERIA|\s+CAPACITY|\s+STANDING|\s+ELIGIBILITY)?|"
                r"TURNOVER\s+CRITERIA)\b",
                re.IGNORECASE,
            ),
            "Financial Criteria",
        ),
        (
            re.compile(
                r"^(?:(?:SECTION|PART|CHAPTER|CLAUSE)\s+[IVXLCDM\d\.]+\s*[:\-\.]?\s*)?"
                r"(PAST(?:\s+EXPERIENCE)?|EXPERIENCE\s+CRITERIA|SIMILAR\s+WORKS?)\b",
                re.IGNORECASE,
            ),
            "Past Experience Criteria",
        ),
        (
            re.compile(
                r"^(?:(?:SECTION|PART|CHAPTER|CLAUSE)\s+[IVXLCDM\d\.]+\s*[:\-\.]?\s*)?"
                r"(TECHNICAL(?:\s+SPECIFICATIONS?|\s+REQUIREMENTS?|\s+EVALUATION)?|"
                r"SCOPE\s+OF\s+WORK)\b",
                re.IGNORECASE,
            ),
            "Technical Requirements",
        ),
        (
            re.compile(
                r"^(?:(?:SECTION|PART|CHAPTER|CLAUSE)\s+[IVXLCDM\d\.]+\s*[:\-\.]?\s*)?"
                r"(RELAXATION(?:\s+OF\s+NORMS)?|EXEMPTIONS?(?:\s+CRITERIA)?|"
                r"PREFERENCE\s+TO\s+MAKE\s+IN\s+INDIA|MSE\s+PREFERENCE)\b",
                re.IGNORECASE,
            ),
            "Policy Exemptions & Relaxations",
        ),
        (
            re.compile(
                r"^(?:(?:SECTION|PART|CHAPTER|CLAUSE|ANNEXURE)\s+[IVXLCDM\d\.]+\s*[:\-\.]?\s*)?"
                r"(MANDATORY\s+DOCUMENTS?|LIST\s+OF\s+DOCUMENTS|CHECKLIST\s+FOR\s+BIDDERS|"
                r"DOCUMENTS\s+TO\s+BE\s+SUBMITTED)\b",
                re.IGNORECASE,
            ),
            "Mandatory Documents Checklist",
        ),
        (
            re.compile(
                r"^(?:(?:SECTION|PART|CHAPTER|CLAUSE)\s+[IVXLCDM\d\.]+\s*[:\-\.]?\s*)?"
                r"(GENERAL\s+TERMS|SPECIAL\s+CONDITIONS\s+OF\s+CONTRACT|COMMERCIAL\s+TERMS)\b",
                re.IGNORECASE,
            ),
            "General Terms & Conditions",
        ),
    ]

    # -------------------------------------------------------------------------
    # 2. PRESCRIPTIVE REQUIREMENT MARKERS (Affirmative/Mandatory Language)
    # -------------------------------------------------------------------------
    PRESCRIPTIVE_MARKERS = [
        re.compile(
            r"\b(?:shall\s+(?:not\s+be\s+less\s+than|have|possess|submit|furnish|produce|be)|"
            r"must\s+(?:have|be|possess|submit|furnish|produce)|"
            r"required\s+to|mandatory|minimum|not\s+less\s+than|at\s+least|"
            r"is\s+to\s+be\s+submitted|to\s+be\s+uploaded|should\s+have|"
            r"eligible|eligibility|qualifying|pre-requisite|condition\s+of\s+eligibility|"
            r"exempted|relaxed|relaxation|waiver)\b",
            re.IGNORECASE,
        ),
    ]

    # Negative patterns: Lines that are boilerplate noise or headers
    IGNORE_PATTERNS = [
        re.compile(r"^(?:Page\s+\d+\s+of\s+\d+|GeM\s+Bid\s+Number|Tender\s+Ref\s*:|Confidential|Date:?\s*\d+)", re.IGNORECASE),
        re.compile(r"^(?:Table\s+of\s+Contents|Index|Disclaimer|Notice\s+Inviting\s+Tender)\s*$", re.IGNORECASE),
    ]

    # -------------------------------------------------------------------------
    # 3. NUMERICAL & ENTITY EXTRACTORS
    # -------------------------------------------------------------------------
    MONETARY_REGEX = re.compile(
        r"(?:Rs\.?|INR|₹)\s*([\d,]+(?:\.\d+)?)\s*(lakhs?|crores?|cr|lacs?|k|m|million|billion)?\b|"
        r"\b([\d,]+(?:\.\d+)?)\s*(lakhs?|crores?|cr|lacs?)\b",
        re.IGNORECASE,
    )
    PERIOD_REGEX = re.compile(
        r"(?:preceding|last|past|during(?:\s+the)?)\s*(?:the\s*)?(\d+|one|two|three|four|five|six|seven|eight|nine|ten)?\s*(?:financial\s*)?(?:years?|yrs?|months?)\b|"
        r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*(?:years?|yrs?)\s*(?:of\s+)?(?:past\s+)?experience\b|"
        r"\b(?:at\s*least|minimum)\s*(\d+|one|two|three|four|five)\s*(?:years?|yrs?)\b",
        re.IGNORECASE,
    )
    PERCENTAGE_REGEX = re.compile(
        r"(\d+(?:\.\d+)?)\s*%",
        re.IGNORECASE,
    )

    WORD_TO_NUM = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    }

    @classmethod
    def parse_numeric_amount(cls, match_groups: Tuple[str, ...]) -> Optional[float]:
        """Converts matched currency and multiplier strings into canonical INR float amount."""
        num_str = match_groups[0] or match_groups[2]
        unit = (match_groups[1] or match_groups[3] or "").lower()

        if not num_str:
            return None

        try:
            val = float(num_str.replace(",", "").strip())
        except ValueError:
            return None

        if "crore" in unit or "cr" in unit:
            return val * 10000000.0
        elif "lakh" in unit or "lac" in unit:
            return val * 100000.0
        elif "million" in unit or unit == "m":
            return val * 1000000.0
        elif unit == "k":
            return val * 1000.0
        return val

    # -------------------------------------------------------------------------
    # 4. CLAUSE DETECTION HEURISTICS
    # -------------------------------------------------------------------------
    @classmethod
    def detect_financial_clause(
        cls, text: str, in_eligibility_section: bool
    ) -> Optional[Tuple[str, List[str], float, Dict[str, Any]]]:
        """Detects annual turnover, net worth, or solvency requirements."""
        matched_kw: List[str] = []
        lower = text.lower()

        if "turnover" in lower:
            matched_kw.append("turnover")
        if "average annual turnover" in lower or "average turnover" in lower:
            matched_kw.append("average_turnover")
        if "annual turnover" in lower:
            matched_kw.append("annual_turnover")
        if "net worth" in lower:
            matched_kw.append("net_worth")
        if "solvency" in lower:
            matched_kw.append("solvency")
        if "working capital" in lower:
            matched_kw.append("working_capital")

        if not matched_kw:
            return None

        # Check for monetary value
        monetary_match = cls.MONETARY_REGEX.search(text)
        period_match = cls.PERIOD_REGEX.search(text)

        # Build parameters
        params: Dict[str, Any] = {"currency": "INR"}
        if monetary_match:
            amt = cls.parse_numeric_amount(monetary_match.groups())
            if amt:
                params["minimum_amount"] = amt
                params["raw_amount"] = monetary_match.group(0).strip()

        if period_match:
            groups = [g for g in period_match.groups() if g]
            if groups:
                period_str = groups[0]
                period_num = cls.WORD_TO_NUM.get(period_str.lower(), None)
                if period_num is None:
                    try:
                        period_num = int(period_str)
                    except ValueError:
                        pass
                if period_num:
                    params["period_years"] = period_num

        # Calculate confidence & reason
        if "turnover" in matched_kw and monetary_match and period_match:
            reason = "turnover + monetary threshold + period"
            confidence = 0.96
        elif monetary_match and (in_eligibility_section or any(p.search(text) for p in cls.PRESCRIPTIVE_MARKERS)):
            metric = matched_kw[0]
            reason = f"{metric} + monetary threshold"
            confidence = 0.92
        elif in_eligibility_section:
            reason = f"{matched_kw[0]} requirement in eligibility section"
            confidence = 0.85
        else:
            return None

        return reason, matched_kw, confidence, params

    @classmethod
    def detect_experience_clause(
        cls, text: str, in_eligibility_section: bool
    ) -> Optional[Tuple[str, List[str], float, Dict[str, Any]]]:
        """Detects past performance, years of experience, or similar work requirements."""
        matched_kw: List[str] = []
        lower = text.lower()

        if "past experience" in lower or "experience criteria" in lower:
            matched_kw.append("past_experience")
        if "similar work" in lower or "similar contracts" in lower or "similar goods" in lower:
            matched_kw.append("similar_work")
        if "years of experience" in lower or "years in business" in lower or "years of operation" in lower:
            matched_kw.append("years_experience")
        if "track record" in lower:
            matched_kw.append("track_record")
        if "completed orders" in lower or "executed contracts" in lower:
            matched_kw.append("executed_orders")

        if not matched_kw:
            return None

        # Look for duration or order counts
        period_match = cls.PERIOD_REGEX.search(text)
        count_match = re.search(r"\b(?:at\s*least|minimum)?\s*(\d+|one|two|three|four|five)\s*(?:similar\s*)?(?:orders?|contracts?|works?|projects?)\b", text, re.IGNORECASE)

        params: Dict[str, Any] = {}
        if period_match:
            groups = [g for g in period_match.groups() if g]
            if groups:
                p_val = groups[0]
                p_num = cls.WORD_TO_NUM.get(p_val.lower()) or (int(p_val) if p_val.isdigit() else None)
                if p_num:
                    params["min_years"] = p_num

        if count_match:
            c_val = count_match.group(1)
            c_num = cls.WORD_TO_NUM.get(c_val.lower()) or (int(c_val) if c_val.isdigit() else None)
            if c_num:
                params["min_orders"] = c_num

        if period_match and any(k in matched_kw for k in ("similar_work", "past_experience", "years_experience")):
            reason = "past experience + duration/order count"
            confidence = 0.95
        elif count_match:
            reason = "similar work execution + order count"
            confidence = 0.93
        elif in_eligibility_section or any(p.search(text) for p in cls.PRESCRIPTIVE_MARKERS):
            reason = "past experience / similar work requirement"
            confidence = 0.88
        else:
            return None

        return reason, matched_kw, confidence, params

    @classmethod
    def detect_oem_clause(
        cls, text: str, in_eligibility_section: bool
    ) -> Optional[Tuple[str, List[str], float, Dict[str, Any]]]:
        """Detects OEM authorization and warranty requirements."""
        matched_kw: List[str] = []
        lower = text.lower()

        if "manufacturer authorization" in lower or "manufacturers authorization" in lower:
            matched_kw.append("manufacturer_authorization")
        if "oem authorization" in lower:
            matched_kw.append("oem_authorization")
        if "original equipment manufacturer" in lower:
            matched_kw.append("original_equipment_manufacturer")
        if "oem" in lower and any(term in lower for term in ("authorization", "authorized", "warranty", "partner", "maf")):
            matched_kw.append("oem_partner_requirement")

        if not matched_kw:
            return None

        params = {"required": True, "type": "OEM_AUTHORIZATION"}
        reason = "oem authorization requirement"
        confidence = 0.95

        return reason, matched_kw, confidence, params

    @classmethod
    def detect_mii_clause(
        cls, text: str, in_eligibility_section: bool
    ) -> Optional[Tuple[str, List[str], float, Dict[str, Any]]]:
        """Detects Make in India (MII) local content requirements."""
        matched_kw: List[str] = []
        lower = text.lower()

        if "make in india" in lower or "preference to make in india" in lower:
            matched_kw.append("make_in_india")
        if "local content" in lower:
            matched_kw.append("local_content")
        if "class-i local supplier" in lower or "class 1 local supplier" in lower:
            matched_kw.append("class_i_supplier")
        if "class-ii local supplier" in lower or "class 2 local supplier" in lower:
            matched_kw.append("class_ii_supplier")

        if not matched_kw:
            return None

        pct_match = cls.PERCENTAGE_REGEX.search(text)
        params: Dict[str, Any] = {"policy": "MAKE_IN_INDIA"}
        if pct_match:
            try:
                params["minimum_local_content_pct"] = float(pct_match.group(1))
            except ValueError:
                pass

        reason = "make in india local content requirement"
        confidence = 0.95 if pct_match else 0.90

        return reason, matched_kw, confidence, params

    @classmethod
    def detect_exemption_clause(
        cls, text: str, in_eligibility_section: bool
    ) -> Optional[Tuple[str, List[str], float, Dict[str, Any]]]:
        """Detects MSE or Startup exemptions and relaxations for turnover/experience."""
        matched_kw: List[str] = []
        lower = text.lower()

        has_beneficiary = any(b in lower for b in ("mse", "mses", "msme", "startup", "startups", "udyam", "dpiit"))
        has_relaxation = any(r in lower for r in ("relaxation", "relaxed", "exemption", "exempted", "waiver", "waived"))

        if not (has_beneficiary and has_relaxation):
            return None

        if "startup" in lower or "startups" in lower:
            matched_kw.append("startup")
        if "mse" in lower or "msme" in lower or "micro and small" in lower:
            matched_kw.append("mse")
        if "turnover" in lower:
            matched_kw.append("turnover_exemption")
        if "experience" in lower:
            matched_kw.append("experience_exemption")
        if "emd" in lower:
            matched_kw.append("emd_exemption")

        applies_to: List[str] = []
        if "startup" in matched_kw:
            applies_to.append("STARTUP")
        if "mse" in matched_kw:
            applies_to.append("MSE")

        exempted_rules: List[str] = []
        if "turnover_exemption" in matched_kw:
            exempted_rules.append("TURNOVER")
        if "experience_exemption" in matched_kw:
            exempted_rules.append("EXPERIENCE")
        if "emd_exemption" in matched_kw:
            exempted_rules.append("EMD")

        params: Dict[str, Any] = {
            "applies_to": applies_to,
            "target_rules": exempted_rules if exempted_rules else ["ALL_ELIGIBILITY"],
            "exemption_type": "FULL",
        }

        reason = "statutory exemption / relaxation clause"
        confidence = 0.95

        return reason, matched_kw, confidence, params

    @classmethod
    def detect_statutory_clause(
        cls, text: str, in_eligibility_section: bool
    ) -> Optional[Tuple[str, List[str], float, Dict[str, Any]]]:
        """Detects GST, PAN, EPF, or other mandatory statutory registrations."""
        matched_kw: List[str] = []
        lower = text.lower()

        if "gst" in lower or "gstin" in lower or "goods and services tax" in lower:
            matched_kw.append("gst")
        if "pan" in lower or "permanent account number" in lower:
            matched_kw.append("pan")
        if "epf" in lower or "epfo" in lower:
            matched_kw.append("epf")
        if "esi" in lower or "esic" in lower:
            matched_kw.append("esi")
        if "income tax return" in lower or "itr" in lower:
            matched_kw.append("itr")

        if not matched_kw:
            return None

        # Requires prescriptive marker or eligibility/documents section
        has_marker = any(p.search(text) for p in cls.PRESCRIPTIVE_MARKERS)
        if not (has_marker or in_eligibility_section):
            return None

        params = {"statutory_ids": [kw.upper() for kw in matched_kw]}
        reason = "statutory tax/registration requirement"
        confidence = 0.92

        return reason, matched_kw, confidence, params

    @classmethod
    def detect_document_clause(
        cls, text: str, in_eligibility_section: bool
    ) -> Optional[Tuple[str, List[str], float, Dict[str, Any]]]:
        """Detects mandatory document submissions (affidavits, undertakings, declarations)."""
        matched_kw: List[str] = []
        lower = text.lower()

        if "affidavit" in lower:
            matched_kw.append("affidavit")
        if "declaration" in lower:
            matched_kw.append("declaration")
        if "undertaking" in lower:
            matched_kw.append("undertaking")
        if "non-blacklisting" in lower or "not blacklisted" in lower or "debarment" in lower:
            matched_kw.append("non_blacklisting")
        if "integrity pact" in lower:
            matched_kw.append("integrity_pact")
        if "power of attorney" in lower or "poa" in lower:
            matched_kw.append("power_of_attorney")
        if "ca certificate" in lower or "chartered accountant" in lower:
            matched_kw.append("ca_certificate")

        if not matched_kw:
            return None

        has_marker = any(p.search(text) for p in cls.PRESCRIPTIVE_MARKERS)
        if not (has_marker or in_eligibility_section):
            return None

        params = {"required_documents": matched_kw}
        reason = "mandatory document / undertaking submission"
        confidence = 0.90

        return reason, matched_kw, confidence, params

    @classmethod
    def detect_technical_clause(
        cls, text: str, in_eligibility_section: bool
    ) -> Optional[Tuple[str, List[str], float, Dict[str, Any]]]:
        """Detects technical standards, ISO certifications, and specifications."""
        matched_kw: List[str] = []
        lower = text.lower()

        if re.search(r"\biso\s*\d{4,5}(?::\d{4})?\b", lower):
            matched_kw.append("iso_certification")
        if "cert-in" in lower or "cert in" in lower:
            matched_kw.append("cert_in")
        if "cve" in lower or "cybersecurity" in lower:
            matched_kw.append("security_standard")
        if "sla" in lower or "service level agreement" in lower or "uptime" in lower:
            matched_kw.append("sla_requirement")

        if not matched_kw:
            return None

        has_marker = any(p.search(text) for p in cls.PRESCRIPTIVE_MARKERS)
        if not (has_marker or in_eligibility_section):
            return None

        params = {"standard": matched_kw[0]}
        reason = "technical standard/certification requirement"
        confidence = 0.88

        return reason, matched_kw, confidence, params

    # -------------------------------------------------------------------------
    # 5. CORE EXTRACTION PIPELINE
    # -------------------------------------------------------------------------
    @classmethod
    def split_into_clauses(cls, text: str) -> List[str]:
        """
        Decomposes document page text into discrete candidate clauses.
        Splits on numbered lists, bullet points, and sentence terminators.
        """
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        clauses: List[str] = []

        for line in lines:
            # Skip boilerplate noise lines
            if any(ign.search(line) for ign in cls.IGNORE_PATTERNS):
                continue

            # Skip lines that are purely section headers (concise titles without sentence terminators)
            is_sec_header = False
            if len(line) < 70 and not line.endswith(".") and not line.endswith(";"):
                for sec_re, _ in cls.SECTION_PATTERNS:
                    if sec_re.search(line):
                        is_sec_header = True
                        break
            if is_sec_header:
                continue

            # Split line on numbered bullet points or semicolons
            # e.g. "(a) ... (b) ..." or "1. ... 2. ..."
            subparts = re.split(r"(?:(?<=[.;])\s+(?=[(]?[a-z\d]{1,2}[).]\s+)|(?<=\.)\s+(?=[A-Z]))", line)
            for sp in subparts:
                cleaned = re.sub(r"^\s*(?:[•\-\*]|\(?\d+\)?[\.\)]|\(?[a-zA-Z]\)[\.\)]?)\s*", "", sp).strip()
                if len(cleaned) >= 20:  # Minimum meaningful clause length
                    clauses.append(cleaned)

        return clauses

    @classmethod
    def extract_from_pages(
        cls,
        pages: List[Union[Dict[str, Any], str]],
    ) -> ClauseExtractionResult:
        """
        Processes a list of page objects or raw text strings.
        Tracks active section state and extracts explainable candidates.
        """
        start_time = time.perf_counter()
        candidates: List[ClauseCandidate] = []
        sections_detected: List[str] = []
        current_section: Optional[str] = None

        for page_idx, page_item in enumerate(pages, start=1):
            if isinstance(page_item, dict):
                page_num = page_item.get("page_number", page_item.get("page", page_idx))
                page_text = page_item.get("text", "")
            else:
                page_num = page_idx
                page_text = str(page_item)

            if not page_text or not page_text.strip():
                continue

            lines = [l.strip() for l in page_text.split("\n") if l.strip()]

            # Section header scanning on raw lines
            for line in lines:
                if len(line) < 70 and not line.endswith(".") and not line.endswith(";"):
                    for sec_regex, sec_name in cls.SECTION_PATTERNS:
                        if sec_regex.search(line):
                            current_section = sec_name
                            if sec_name not in sections_detected:
                                sections_detected.append(sec_name)
                            break

            # Decompose page into candidate clauses
            clauses = cls.split_into_clauses(page_text)
            in_eligibility = current_section in (
                "Eligibility Criteria",
                "Financial Criteria",
                "Past Experience Criteria",
                "Policy Exemptions & Relaxations",
                "Mandatory Documents Checklist",
            )

            for clause_text in clauses:
                candidate = cls._evaluate_clause(
                    text=clause_text,
                    page=page_num,
                    section=current_section,
                    in_eligibility=in_eligibility,
                )
                if candidate:
                    candidates.append(candidate)

        total_time_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.info(
            f"Extracted {len(candidates)} candidate clauses across {len(pages)} pages "
            f"({len(sections_detected)} sections detected) in {total_time_ms}ms"
        )

        return ClauseExtractionResult(
            total_candidates=len(candidates),
            candidates=candidates,
            sections_detected=sections_detected,
            processing_time_ms=total_time_ms,
        )

    @classmethod
    def extract_from_text(
        cls,
        text: str,
        page: int = 1,
        default_section: Optional[str] = None,
    ) -> ClauseExtractionResult:
        """Convenience method to process single page or monolithic document text."""
        return cls.extract_from_pages([{"page_number": page, "text": text}])

    @classmethod
    def _evaluate_clause(
        cls,
        text: str,
        page: int,
        section: Optional[str],
        in_eligibility: bool,
    ) -> Optional[ClauseCandidate]:
        """
        Runs deterministic detectors against a candidate clause.
        Returns a structured ClauseCandidate if an eligibility pattern is matched.
        """
        # Order of evaluation: Exemptions -> Financial -> Experience -> OEM -> MII -> Statutory -> Document -> Technical

        # 1. Exemption / Relaxation
        ex_res = cls.detect_exemption_clause(text, in_eligibility)
        if ex_res:
            reason, kws, conf, params = ex_res
            return ClauseCandidate(
                page=page,
                section=section,
                source_text=text,
                candidate_type=RequirementType.EXEMPTION.value,
                detection_reason=reason,
                detected_keywords=kws,
                confidence=conf,
                rule="STATUTORY_EXEMPTION",
                parameters=params,
                is_mandatory=False,
            )

        # 2. Financial Criteria
        fin_res = cls.detect_financial_clause(text, in_eligibility)
        if fin_res:
            reason, kws, conf, params = fin_res
            rule_id = "MINIMUM_ANNUAL_TURNOVER" if "turnover" in kws else "FINANCIAL_CAPACITY"
            return ClauseCandidate(
                page=page,
                section=section,
                source_text=text,
                candidate_type=RequirementType.FINANCIAL.value,
                detection_reason=reason,
                detected_keywords=kws,
                confidence=conf,
                rule=rule_id,
                parameters=params,
                is_mandatory=True,
            )

        # 3. Experience Criteria
        exp_res = cls.detect_experience_clause(text, in_eligibility)
        if exp_res:
            reason, kws, conf, params = exp_res
            return ClauseCandidate(
                page=page,
                section=section,
                source_text=text,
                candidate_type=RequirementType.EXPERIENCE.value,
                detection_reason=reason,
                detected_keywords=kws,
                confidence=conf,
                rule="PAST_EXPERIENCE",
                parameters=params,
                is_mandatory=True,
            )

        # 4. OEM Authorization
        oem_res = cls.detect_oem_clause(text, in_eligibility)
        if oem_res:
            reason, kws, conf, params = oem_res
            return ClauseCandidate(
                page=page,
                section=section,
                source_text=text,
                candidate_type=RequirementType.OEM.value,
                detection_reason=reason,
                detected_keywords=kws,
                confidence=conf,
                rule="OEM_AUTHORIZATION",
                parameters=params,
                is_mandatory=True,
            )

        # 5. Make in India
        mii_res = cls.detect_mii_clause(text, in_eligibility)
        if mii_res:
            reason, kws, conf, params = mii_res
            return ClauseCandidate(
                page=page,
                section=section,
                source_text=text,
                candidate_type=RequirementType.MII.value,
                detection_reason=reason,
                detected_keywords=kws,
                confidence=conf,
                rule="MII_LOCAL_CONTENT",
                parameters=params,
                is_mandatory=True,
            )

        # 6. Statutory Registrations
        stat_res = cls.detect_statutory_clause(text, in_eligibility)
        if stat_res:
            reason, kws, conf, params = stat_res
            return ClauseCandidate(
                page=page,
                section=section,
                source_text=text,
                candidate_type=RequirementType.STATUTORY.value,
                detection_reason=reason,
                detected_keywords=kws,
                confidence=conf,
                rule="STATUTORY_REGISTRATION",
                parameters=params,
                is_mandatory=True,
            )

        # 7. Mandatory Documents Checklist
        doc_res = cls.detect_document_clause(text, in_eligibility)
        if doc_res:
            reason, kws, conf, params = doc_res
            return ClauseCandidate(
                page=page,
                section=section,
                source_text=text,
                candidate_type=RequirementType.DOCUMENT.value,
                detection_reason=reason,
                detected_keywords=kws,
                confidence=conf,
                rule="MANDATORY_DOCUMENT",
                parameters=params,
                is_mandatory=True,
            )

        # 8. Technical Standards
        tech_res = cls.detect_technical_clause(text, in_eligibility)
        if tech_res:
            reason, kws, conf, params = tech_res
            return ClauseCandidate(
                page=page,
                section=section,
                source_text=text,
                candidate_type=RequirementType.TECHNICAL.value,
                detection_reason=reason,
                detected_keywords=kws,
                confidence=conf,
                rule="TECHNICAL_SPECIFICATION",
                parameters=params,
                is_mandatory=True,
            )

        return None


tender_clause_extractor = TenderClauseExtractor()
extract_clauses = tender_clause_extractor.extract_from_pages
extract_clauses_from_text = tender_clause_extractor.extract_from_text
