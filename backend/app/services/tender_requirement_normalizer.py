import logging
import re
from typing import Any, Dict, List, Optional, Tuple, Union

from app.models.enums import RequirementType
from app.schemas.tender_clause import ClauseCandidate
from app.schemas.tender_requirement_normalizer import (
    NormalizationResult,
    NormalizationStatus,
    NormalizedRequirement,
)

logger = logging.getLogger("app.services.tender_requirement_normalizer")


class TenderRequirementNormalizer:
    """
    Deterministic requirement detection and normalization engine (Phase 08).
    Translates raw candidate clauses into standardized TenderRequirement specifications,
    normalizing Indian currency, durations, and statutory requirements.
    Marks vague or unquantified clauses as AMBIGUOUS without guessing.
    """

    WORD_TO_NUM = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    }

    # -------------------------------------------------------------------------
    # 1. INDIAN CURRENCY NORMALIZATION
    # -------------------------------------------------------------------------
    # Matches: ₹15 lakh, Rs. 15 lakh, INR 1,500,000, Rs 15,00,000, 15 Lakhs, 4.50 Crores, 50k
    CURRENCY_REGEX = re.compile(
        r"(?:₹|Rs\.?|INR)?\s*([\d,]+(?:\.\d+)?)\s*(crores?|cr|lakhs?|lacs?|lac|thousand|k|million|m)?\b",
        re.IGNORECASE,
    )

    @classmethod
    def normalize_indian_currency(cls, text: str) -> Optional[int]:
        """
        Parses diverse Indian monetary expressions into a canonical INR integer.
        e.g. '₹15 lakh', 'Rs. 15 lakh', 'INR 1,500,000', 'Rs 15,00,000', '15 Lakhs' -> 1500000
        """
        # Find matches that are either prefixed with a currency symbol or suffixed with currency units
        matches = cls.CURRENCY_REGEX.finditer(text)
        candidates: List[Tuple[float, str]] = []

        for m in matches:
            full_match = m.group(0).strip()
            num_str = m.group(1)
            unit = (m.group(2) or "").lower()

            if not num_str:
                continue

            # Must have either a currency symbol in match or an explicit unit (crore, lakh, etc.)
            has_sym = any(sym in full_match for sym in ("₹", "Rs", "rs", "INR", "inr"))
            has_unit = bool(unit)

            # Or if formatted with commas (e.g. 15,00,000 or 1,500,000)
            has_comma = "," in num_str

            if not (has_sym or has_unit or has_comma):
                continue

            try:
                val = float(num_str.replace(",", "").strip())
            except ValueError:
                continue

            # Ignore standalone years (e.g. 2023, 2024) unless explicit currency symbol
            if not has_sym and not has_unit and 1900 <= val <= 2100:
                continue

            if "crore" in unit or "cr" in unit:
                multiplier = 10000000.0
            elif "lakh" in unit or "lac" in unit:
                multiplier = 100000.0
            elif "million" in unit or unit == "m":
                multiplier = 1000000.0
            elif "thousand" in unit or unit == "k":
                multiplier = 1000.0
            else:
                multiplier = 1.0

            total_amount = val * multiplier
            candidates.append((total_amount, full_match))

        if not candidates:
            return None

        # Return the most prominent monetary amount (highest or first relevant)
        # For turnover thresholds, take the maximum detected threshold
        best_amount = max(c[0] for c in candidates)
        return int(round(best_amount))

    # -------------------------------------------------------------------------
    # 2. TIME EXPRESSION NORMALIZATION
    # -------------------------------------------------------------------------
    # Matches: previous 3 years, preceding three years, last three financial years, 5 years experience
    TIME_REGEX = re.compile(
        r"(?:preceding|previous|last|past|during(?:\s+the)?)\s*(?:the\s*)?"
        r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten)?\s*(?:financial\s*)?"
        r"(years?|yrs?|months?)\b|"
        r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*"
        r"(years?|yrs?|months?)\s*(?:of\s+)?(?:past\s+)?(?:experience|operation|business)?\b",
        re.IGNORECASE,
    )

    @classmethod
    def normalize_time_expression(cls, text: str) -> Optional[Dict[str, Any]]:
        """
        Normalizes phrases like 'preceding three years', 'last three financial years',
        'previous 3 years' into standard: {"period": 3, "period_unit": "YEARS"}.
        """
        match = cls.TIME_REGEX.search(text)
        if not match:
            return None

        # Find which group captured the number and unit
        g1_num, g1_unit = match.group(1), match.group(2)
        g2_num, g2_unit = match.group(3), match.group(4)

        raw_num = g1_num or g2_num
        raw_unit = (g1_unit or g2_unit or "years").lower()

        if not raw_num:
            return None

        period_int = cls.WORD_TO_NUM.get(raw_num.lower())
        if period_int is None:
            try:
                period_int = int(raw_num)
            except ValueError:
                return None

        period_unit = "MONTHS" if "month" in raw_unit else "YEARS"

        return {
            "period": period_int,
            "period_unit": period_unit,
        }

    # -------------------------------------------------------------------------
    # 3. RULE NORMALIZATION DISPATCHER
    # -------------------------------------------------------------------------
    @classmethod
    def normalize_clause(
        cls,
        clause: Union[ClauseCandidate, Dict[str, Any], str],
        page: Optional[int] = None,
        section: Optional[str] = None,
        page_start: Optional[int] = None,
        page_end: Optional[int] = None,
        section_id: Optional[str] = None,
        document_id: Optional[str] = None,
    ) -> NormalizedRequirement:
        """
        Translates a single candidate clause into a NormalizedRequirement.
        Resolves standard procurement rules deterministically.
        Marks incomplete, vague, or non-quantified criteria as AMBIGUOUS without guessing.
        """
        # Unpack input
        if isinstance(clause, ClauseCandidate):
            source_text = clause.source_text
            source_page = clause.page
            p_start = clause.page_start or clause.page
            p_end = clause.page_end or clause.page
            source_section = clause.section
            sec_id = clause.section_id
            doc_id = clause.document_id
            cand_type = clause.candidate_type
            cand_confidence = clause.confidence
            requires_semantic = clause.requires_semantic_interpretation
        elif isinstance(clause, dict):
            source_text = clause.get("source_text", clause.get("text", ""))
            source_page = clause.get("page", page)
            p_start = clause.get("page_start", page_start or source_page)
            p_end = clause.get("page_end", page_end or source_page)
            source_section = clause.get("section", section)
            sec_id = clause.get("section_id", section_id)
            doc_id = clause.get("document_id", document_id)
            cand_type = clause.get("candidate_type", clause.get("type"))
            cand_confidence = float(clause.get("confidence", 0.90))
            requires_semantic = clause.get("requires_semantic_interpretation", False)
        else:
            source_text = str(clause)
            source_page = page
            p_start = page_start or page
            p_end = page_end or page
            source_section = section
            sec_id = section_id
            doc_id = document_id
            cand_type = None
            cand_confidence = 0.90
            requires_semantic = False

        clean_text = source_text.strip()
        lower = clean_text.lower()

        # ---------------------------------------------------------------------
        # Rule 15: EXPLICIT EXEMPTIONS (Startup & MSE)
        # ---------------------------------------------------------------------
        has_beneficiary = any(b in lower for b in ("startup", "startups", "mse", "mses", "msme", "dpiit", "udyam"))
        has_waiver = any(w in lower for w in ("relaxation", "relaxed", "exemption", "exempted", "waiver", "waived"))

        if has_beneficiary and has_waiver:
            applies_to: List[str] = []
            if "startup" in lower:
                applies_to.append("STARTUP")
            if "mse" in lower or "msme" in lower or "micro and small" in lower:
                applies_to.append("MSE")

            target_rules: List[str] = []
            if "turnover" in lower:
                target_rules.append("AVERAGE_TURNOVER")
            if "experience" in lower:
                target_rules.append("PAST_EXPERIENCE")
            if "emd" in lower:
                target_rules.append("EMD")

            target_rule_name = target_rules[0] if len(target_rules) == 1 else "ELIGIBILITY_CRITERIA"
            rule_id = f"{applies_to[0]}_{target_rule_name}_EXEMPTION" if applies_to else "STATUTORY_EXEMPTION"

            params: Dict[str, Any] = {
                "applies_to": applies_to if applies_to else ["STARTUP", "MSE"],
                "target_rule": target_rule_name,
                "target_rules": target_rules if target_rules else ["ALL_ELIGIBILITY"],
                "exemption_type": "FULL",
            }

            return NormalizedRequirement(
                status=NormalizationStatus.NORMALIZED,
                type=RequirementType.EXEMPTION.value,
                rule=rule_id,
                description=f"Statutory relaxation of {target_rule_name} for {', '.join(params['applies_to'])}",
                parameters=params,
                mandatory=False,
                confidence=0.98,
                source_page=source_page,
                page_start=p_start,
                page_end=p_end,
                source_section=source_section,
                section_id=sec_id,
                document_id=doc_id,
                source_text=clean_text,
            )

        # ---------------------------------------------------------------------
        # Rule: EMD / BID SECURITY
        # ---------------------------------------------------------------------
        if "emd" in lower or "earnest money" in lower or "bid security" in lower:
            amount = cls.normalize_indian_currency(clean_text)
            pct_match = re.search(r"(\d+(?:\.\d+)?)\s*%", clean_text)
            pct_val = float(pct_match.group(1)) if pct_match else None
            is_declaration = "declaration" in lower or "bid security declaration" in lower

            params: Dict[str, Any] = {"currency": "INR", "operator": ">="}
            if amount:
                params["amount"] = amount
                params["value"] = amount
            if pct_val:
                params["percentage"] = pct_val
            if is_declaration:
                params["declaration_accepted"] = True

            if not (amount or pct_val or is_declaration):
                return NormalizedRequirement(
                    status=NormalizationStatus.AMBIGUOUS,
                    type=RequirementType.FINANCIAL.value,
                    rule="EMD_REQUIREMENT",
                    source_page=source_page,
                    page_start=p_start,
                    page_end=p_end,
                    source_section=source_section,
                    section_id=sec_id,
                    document_id=doc_id,
                    source_text=clean_text,
                    requires_semantic_interpretation=True,
                    ambiguity_reason="Missing quantifiable EMD amount or percentage threshold",
                    confidence=None,
                )

            desc = f"Mandatory EMD submission: {clean_text}"
            return NormalizedRequirement(
                status=NormalizationStatus.NORMALIZED,
                type=RequirementType.FINANCIAL.value,
                rule="EMD_REQUIREMENT",
                description=desc,
                parameters=params,
                mandatory=True,
                confidence=0.98 if (amount or pct_val) else 0.92,
                source_page=source_page,
                page_start=p_start,
                page_end=p_end,
                source_section=source_section,
                section_id=sec_id,
                document_id=doc_id,
                source_text=clean_text,
            )

        # ---------------------------------------------------------------------
        # Rule: PERFORMANCE SECURITY / PBG
        # ---------------------------------------------------------------------
        if "performance security" in lower or "performance bank guarantee" in lower or "pbg" in lower or "contract performance" in lower:
            amount = cls.normalize_indian_currency(clean_text)
            pct_match = re.search(r"(\d+(?:\.\d+)?)\s*%", clean_text)
            pct_val = float(pct_match.group(1)) if pct_match else None

            params: Dict[str, Any] = {"currency": "INR", "operator": ">="}
            if pct_val:
                params["percentage"] = pct_val
            if amount:
                params["amount"] = amount
                params["value"] = amount

            if not (pct_val or amount):
                return NormalizedRequirement(
                    status=NormalizationStatus.AMBIGUOUS,
                    type=RequirementType.FINANCIAL.value,
                    rule="PERFORMANCE_SECURITY",
                    source_page=source_page,
                    page_start=p_start,
                    page_end=p_end,
                    source_section=source_section,
                    section_id=sec_id,
                    document_id=doc_id,
                    source_text=clean_text,
                    requires_semantic_interpretation=True,
                    ambiguity_reason="Missing quantifiable percentage or amount for performance security",
                    confidence=None,
                )

            desc = f"Performance Security requirement of {pct_val}% of contract value" if pct_val else f"Performance Security of INR {amount:,}"
            return NormalizedRequirement(
                status=NormalizationStatus.NORMALIZED,
                type=RequirementType.FINANCIAL.value,
                rule="PERFORMANCE_SECURITY",
                description=desc,
                parameters=params,
                mandatory=True,
                confidence=0.96,
                source_page=source_page,
                page_start=p_start,
                page_end=p_end,
                source_section=source_section,
                section_id=sec_id,
                document_id=doc_id,
                source_text=clean_text,
            )

        # ---------------------------------------------------------------------
        # Rule: ESTIMATED TENDER VALUE
        # ---------------------------------------------------------------------
        if "estimated value" in lower or "tender value" in lower or "estimated cost" in lower:
            amount = cls.normalize_indian_currency(clean_text)
            if amount:
                return NormalizedRequirement(
                    status=NormalizationStatus.NORMALIZED,
                    type=RequirementType.FINANCIAL.value,
                    rule="ESTIMATED_TENDER_VALUE",
                    description=f"Estimated Tender Value: INR {amount:,}",
                    parameters={"estimated_value": amount, "value": amount, "currency": "INR"},
                    mandatory=False,
                    confidence=0.96,
                    source_page=source_page,
                    page_start=p_start,
                    page_end=p_end,
                    source_section=source_section,
                    section_id=sec_id,
                    document_id=doc_id,
                    source_text=clean_text,
                )

        # ---------------------------------------------------------------------
        # Rule 1 & 2: TURNOVER (Average Annual Turnover vs Minimum Turnover)
        # ---------------------------------------------------------------------
        if "turnover" in lower:
            amount = cls.normalize_indian_currency(clean_text)
            time_info = cls.normalize_time_expression(clean_text)

            is_average = any(avg in lower for avg in ("average", "avg", "annual average"))
            rule_name = "AVERAGE_TURNOVER" if is_average else "MINIMUM_TURNOVER"

            if amount is None:
                return NormalizedRequirement(
                    status=NormalizationStatus.AMBIGUOUS,
                    type=RequirementType.FINANCIAL.value,
                    rule=rule_name,
                    source_page=source_page,
                    page_start=p_start,
                    page_end=p_end,
                    source_section=source_section,
                    section_id=sec_id,
                    document_id=doc_id,
                    source_text=clean_text,
                    requires_semantic_interpretation=True,
                    ambiguity_reason="Missing quantifiable monetary threshold for turnover",
                    confidence=None,
                )

            params = {
                "minimum": amount,
                "value": amount,
                "operator": ">=",
                "currency": "INR",
            }
            if time_info:
                params["period"] = time_info["period"]
                params["period_unit"] = time_info["period_unit"]

            desc = f"Minimum {rule_name.replace('_', ' ').lower()} of INR {amount:,}"
            if time_info:
                desc += f" over preceding {time_info['period']} {time_info['period_unit'].lower()}"

            return NormalizedRequirement(
                status=NormalizationStatus.NORMALIZED,
                type=RequirementType.FINANCIAL.value,
                rule=rule_name,
                description=desc,
                parameters=params,
                mandatory=True,
                confidence=0.98 if time_info else 0.94,
                source_page=source_page,
                page_start=p_start,
                page_end=p_end,
                source_section=source_section,
                section_id=sec_id,
                document_id=doc_id,
                source_text=clean_text,
            )

        # ---------------------------------------------------------------------
        # Rule 3: NET WORTH
        # ---------------------------------------------------------------------
        if "net worth" in lower or "networth" in lower:
            amount = cls.normalize_indian_currency(clean_text)
            is_positive = "positive" in lower

            params: Dict[str, Any] = {"currency": "INR", "operator": ">="}
            if amount:
                params["minimum"] = amount
                params["value"] = amount
            elif is_positive:
                params["condition"] = "POSITIVE"
            else:
                return NormalizedRequirement(
                    status=NormalizationStatus.AMBIGUOUS,
                    type=RequirementType.FINANCIAL.value,
                    rule="NET_WORTH",
                    source_page=source_page,
                    page_start=p_start,
                    page_end=p_end,
                    source_section=source_section,
                    section_id=sec_id,
                    document_id=doc_id,
                    source_text=clean_text,
                    requires_semantic_interpretation=True,
                    ambiguity_reason="Missing quantifiable net worth threshold or positive condition",
                    confidence=None,
                )

            return NormalizedRequirement(
                status=NormalizationStatus.NORMALIZED,
                type=RequirementType.FINANCIAL.value,
                rule="NET_WORTH",
                description="Bidder must have positive/specified net worth",
                parameters=params,
                mandatory=True,
                confidence=0.95,
                source_page=source_page,
                page_start=p_start,
                page_end=p_end,
                source_section=source_section,
                section_id=sec_id,
                document_id=doc_id,
                source_text=clean_text,
            )

        # ---------------------------------------------------------------------
        # Rule 4, 5, 6: EXPERIENCE (Similar Work, Completed Projects, Experience Period)
        # ---------------------------------------------------------------------
        if any(exp in lower for exp in ("experience", "similar work", "similar contracts", "completed works", "executed orders", "past performance")):
            time_info = cls.normalize_time_expression(clean_text)
            order_match = re.search(
                r"\b(?:at\s*least|minimum)?\s*(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*"
                r"(?:similar\s*)?(?:orders?|contracts?|works?|projects?)\b",
                clean_text,
                re.IGNORECASE,
            )

            min_orders: Optional[int] = None
            if order_match:
                raw_ord = order_match.group(1)
                min_orders = cls.WORD_TO_NUM.get(raw_ord.lower()) or (int(raw_ord) if raw_ord.isdigit() else None)

            is_similar = any(s in lower for s in ("similar work", "similar contract", "similar project", "similar goods", "similar service"))

            # Determine specific rule
            if min_orders is not None:
                rule_name = "COMPLETED_PROJECTS"
                params = {"min_completed_orders": min_orders, "scope": "SIMILAR_WORK" if is_similar else "GENERAL", "operator": ">="}
                if time_info:
                    params["within_period"] = time_info["period"]
                    params["period_unit"] = time_info["period_unit"]
            elif is_similar and time_info:
                rule_name = "SIMILAR_WORK_EXPERIENCE"
                params = {"scope": "SIMILAR_WORK", "min_years": time_info["period"], "period_unit": time_info["period_unit"], "operator": ">="}
            elif time_info:
                rule_name = "EXPERIENCE_PERIOD"
                params = {"min_years": time_info["period"], "period_unit": time_info["period_unit"], "operator": ">="}
            else:
                return NormalizedRequirement(
                    status=NormalizationStatus.AMBIGUOUS,
                    type=RequirementType.EXPERIENCE.value,
                    rule="PAST_EXPERIENCE",
                    source_page=source_page,
                    page_start=p_start,
                    page_end=p_end,
                    source_section=source_section,
                    section_id=sec_id,
                    document_id=doc_id,
                    source_text=clean_text,
                    requires_semantic_interpretation=True,
                    ambiguity_reason="Missing quantifiable duration (years) or completed order count",
                    confidence=None,
                )

            return NormalizedRequirement(
                status=NormalizationStatus.NORMALIZED,
                type=RequirementType.EXPERIENCE.value,
                rule=rule_name,
                description=f"Requirement for {rule_name.replace('_', ' ').lower()}",
                parameters=params,
                mandatory=True,
                confidence=0.95,
                source_page=source_page,
                page_start=p_start,
                page_end=p_end,
                source_section=source_section,
                section_id=sec_id,
                document_id=doc_id,
                source_text=clean_text,
            )

        # ---------------------------------------------------------------------
        # Rule 7 & 8: GST and PAN Statutory Requirements
        # ---------------------------------------------------------------------
        has_gst = any(g in lower for g in ("gst", "gstin", "goods and services tax"))
        has_pan = any(p in lower for p in ("pan", "pan card", "permanent account number"))

        if has_gst and has_pan:
            return NormalizedRequirement(
                status=NormalizationStatus.NORMALIZED,
                type=RequirementType.STATUTORY.value,
                rule="GST_AND_PAN_REGISTRATION",
                description="Bidder must possess valid GSTIN and PAN registrations",
                parameters={"statutory_documents": ["GSTIN", "PAN"], "active_status_required": True},
                mandatory=True,
                confidence=0.98,
                source_page=source_page,
                page_start=p_start,
                page_end=p_end,
                source_section=source_section,
                section_id=sec_id,
                document_id=doc_id,
                source_text=clean_text,
            )
        elif has_gst:
            return NormalizedRequirement(
                status=NormalizationStatus.NORMALIZED,
                type=RequirementType.STATUTORY.value,
                rule="GST_REGISTRATION",
                description="Bidder must possess valid GSTIN registration",
                parameters={"document_type": "GSTIN", "active_status_required": True},
                mandatory=True,
                confidence=0.98,
                source_page=source_page,
                page_start=p_start,
                page_end=p_end,
                source_section=source_section,
                section_id=sec_id,
                document_id=doc_id,
                source_text=clean_text,
            )
        elif has_pan:
            return NormalizedRequirement(
                status=NormalizationStatus.NORMALIZED,
                type=RequirementType.STATUTORY.value,
                rule="PAN_REQUIREMENT",
                description="Bidder must possess valid PAN card",
                parameters={"document_type": "PAN"},
                mandatory=True,
                confidence=0.98,
                source_page=source_page,
                page_start=p_start,
                page_end=p_end,
                source_section=source_section,
                section_id=sec_id,
                document_id=doc_id,
                source_text=clean_text,
            )

        # ---------------------------------------------------------------------
        # Rule 9: License / Statutory Registrations (EPF, ESI, Labor, Factory)
        # ---------------------------------------------------------------------
        if any(lic in lower for lic in ("epf", "epfo", "esi", "esic", "labor license", "factory license", "pollution control")):
            found_lics = []
            if "epf" in lower or "epfo" in lower:
                found_lics.append("EPF")
            if "esi" in lower or "esic" in lower:
                found_lics.append("ESI")
            if "labor" in lower:
                found_lics.append("LABOR_LICENSE")

            return NormalizedRequirement(
                status=NormalizationStatus.NORMALIZED,
                type=RequirementType.STATUTORY.value,
                rule="STATUTORY_LICENSE",
                description=f"Mandatory statutory registration for: {', '.join(found_lics)}",
                parameters={"licenses": found_lics},
                mandatory=True,
                confidence=0.94,
                source_page=source_page,
                page_start=p_start,
                page_end=p_end,
                source_section=source_section,
                section_id=sec_id,
                document_id=doc_id,
                source_text=clean_text,
            )

        # ---------------------------------------------------------------------
        # Rule 10: OEM Authorization
        # ---------------------------------------------------------------------
        if any(o in lower for o in ("oem", "manufacturer authorization", "manufacturers authorization", "maf")):
            return NormalizedRequirement(
                status=NormalizationStatus.NORMALIZED,
                type=RequirementType.OEM.value,
                rule="OEM_AUTHORIZATION",
                description="Valid OEM Manufacturer Authorization Form (MAF) required for non-OEM bidders",
                parameters={"authorization_type": "MAF", "required": True},
                mandatory=True,
                confidence=0.96,
                source_page=source_page,
                page_start=p_start,
                page_end=p_end,
                source_section=source_section,
                section_id=sec_id,
                document_id=doc_id,
                source_text=clean_text,
            )

        # ---------------------------------------------------------------------
        # Rule 11: Make in India (MII) Local Content
        # ---------------------------------------------------------------------
        if any(m in lower for m in ("make in india", "local content", "class-i local supplier", "class-ii local supplier")):
            pct_match = re.search(r"(\d+(?:\.\d+)?)\s*%", clean_text)
            pct_val = float(pct_match.group(1)) if pct_match else None

            supplier_class = "CLASS_I" if "class-i" in lower or "class 1" in lower else "CLASS_II" if "class-ii" in lower else None

            params = {"policy": "MAKE_IN_INDIA", "operator": ">="}
            if pct_val is not None:
                params["minimum_local_content_pct"] = pct_val
            if supplier_class:
                params["supplier_class"] = supplier_class

            return NormalizedRequirement(
                status=NormalizationStatus.NORMALIZED,
                type=RequirementType.MII.value,
                rule="MII_LOCAL_CONTENT",
                description=f"Make in India local content requirement ({pct_val or 'prescribed'}%)",
                parameters=params,
                mandatory=True,
                confidence=0.96 if pct_val is not None else 0.90,
                source_page=source_page,
                page_start=p_start,
                page_end=p_end,
                source_section=source_section,
                section_id=sec_id,
                document_id=doc_id,
                source_text=clean_text,
            )

        # ---------------------------------------------------------------------
        # Rule 12: MSE Conditions
        # ---------------------------------------------------------------------
        if any(m in lower for m in ("mse", "msme", "micro and small")):
            return NormalizedRequirement(
                status=NormalizationStatus.NORMALIZED,
                type=RequirementType.MSE.value,
                rule="MSE_PREFERENCE",
                description="Public Procurement Policy for Micro and Small Enterprises (MSEs) compliance",
                parameters={"target_group": "MSE", "policy": "MSE_PROCUREMENT_POLICY"},
                mandatory=False,
                confidence=0.92,
                source_page=source_page,
                page_start=p_start,
                page_end=p_end,
                source_section=source_section,
                section_id=sec_id,
                document_id=doc_id,
                source_text=clean_text,
            )

        # ---------------------------------------------------------------------
        # Rule 13: Startup Conditions
        # ---------------------------------------------------------------------
        if "startup" in lower or "dpiit" in lower:
            return NormalizedRequirement(
                status=NormalizationStatus.NORMALIZED,
                type=RequirementType.STARTUP.value,
                rule="STARTUP_CRITERIA",
                description="DPIIT recognized Startup qualification criteria",
                parameters={"target_group": "STARTUP", "recognition": "DPIIT"},
                mandatory=False,
                confidence=0.92,
                source_page=source_page,
                page_start=p_start,
                page_end=p_end,
                source_section=source_section,
                section_id=sec_id,
                document_id=doc_id,
                source_text=clean_text,
            )

        # ---------------------------------------------------------------------
        # Rule: QUALITY / ISO CERTIFICATIONS
        # ---------------------------------------------------------------------
        if any(cert in lower for cert in ("iso 9001", "iso 27001", "iso 14001", "iso 45001", "cmmi", "bis", "ce certification")):
            matched_certs = [c.upper() for c in ("iso 9001", "iso 27001", "iso 14001", "iso 45001", "cmmi", "bis") if c in lower]
            return NormalizedRequirement(
                status=NormalizationStatus.NORMALIZED,
                type=RequirementType.TECHNICAL.value,
                rule="QUALITY_CERTIFICATION",
                description=f"Mandatory quality/security certification: {', '.join(matched_certs)}",
                parameters={"certifications": matched_certs},
                mandatory=True,
                confidence=0.96,
                source_page=source_page,
                page_start=p_start,
                page_end=p_end,
                source_section=source_section,
                section_id=sec_id,
                document_id=doc_id,
                source_text=clean_text,
            )

        # ---------------------------------------------------------------------
        # Rule 14: Required Documents & Certificates (Affidavit, Undertaking, Non-Blacklisting, Balance Sheet)
        # ---------------------------------------------------------------------
        if any(doc in lower for doc in ("affidavit", "undertaking", "non-blacklisting", "integrity pact", "power of attorney", "ca certificate", "audited balance sheet", "audited financial")):
            doc_type = "NON_BLACKLISTING_AFFIDAVIT" if ("blacklisting" in lower or "debarred" in lower) else \
                       "INTEGRITY_PACT" if "integrity pact" in lower else \
                       "POWER_OF_ATTORNEY" if "power of attorney" in lower or "poa" in lower else \
                       "CA_CERTIFICATE" if "ca certificate" in lower or "chartered accountant" in lower else \
                       "AUDITED_FINANCIAL_STATEMENT" if ("audited balance" in lower or "audited financial" in lower) else \
                       "UNDERTAKING"

            is_notarized = "notarized" in lower or "stamp paper" in lower

            return NormalizedRequirement(
                status=NormalizationStatus.NORMALIZED,
                type=RequirementType.DOCUMENT.value,
                rule="REQUIRED_DOCUMENT",
                description=f"Submission of mandatory document: {doc_type}",
                parameters={"document_type": doc_type, "notarized": is_notarized},
                mandatory=True,
                confidence=0.94,
                source_page=source_page,
                page_start=p_start,
                page_end=p_end,
                source_section=source_section,
                section_id=sec_id,
                document_id=doc_id,
                source_text=clean_text,
            )

        # ---------------------------------------------------------------------
        # Fallback: Ambiguous / Unresolved clause (NO GUESSING)
        # ---------------------------------------------------------------------
        return NormalizedRequirement(
            status=NormalizationStatus.AMBIGUOUS,
            type=cand_type or RequirementType.OTHER.value,
            rule="UNRESOLVED_CRITERIA",
            source_page=source_page,
            page_start=p_start,
            page_end=p_end,
            source_section=source_section,
            section_id=sec_id,
            document_id=doc_id,
            source_text=clean_text,
            requires_semantic_interpretation=True,
            ambiguity_reason="Clause requires manual or LLM interpretation to determine precise compliance parameters",
            confidence=None,
        )

    @classmethod
    def normalize_candidates(
        cls,
        candidates: List[Union[ClauseCandidate, Dict[str, Any]]],
    ) -> NormalizationResult:
        """Processes a list of candidate clauses and produces a batch NormalizationResult."""
        results: List[NormalizedRequirement] = []
        norm_count = 0
        amb_count = 0

        for cand in candidates:
            normalized = cls.normalize_clause(cand)
            results.append(normalized)
            if normalized.status == NormalizationStatus.NORMALIZED:
                norm_count += 1
            else:
                amb_count += 1

        logger.info(f"Normalized {norm_count}/{len(candidates)} requirements ({amb_count} ambiguous)")
        return NormalizationResult(
            total_evaluated=len(candidates),
            normalized_count=norm_count,
            ambiguous_count=amb_count,
            requirements=results,
        )

    @classmethod
    def normalize_sections(
        cls,
        sections: List[Any],
        document_id: Optional[str] = None,
    ) -> NormalizationResult:
        """
        Directly extracts and normalizes tender requirements from bounded DetectedTenderSection objects.
        """
        from app.services.tender_clause_extractor import extract_clauses_from_sections
        extract_res = extract_clauses_from_sections(sections, document_id=document_id)
        return cls.normalize_candidates(extract_res.candidates)

    @classmethod
    def resolve_ambiguous_requirements(
        cls,
        requirements: List[NormalizedRequirement],
        gateway: Optional[Any] = None,
    ) -> List[NormalizedRequirement]:
        """
        Selectively escalates only ambiguous requirements (requires_semantic_interpretation=True)
        to the AI Gateway with strict grounding validation and fallback preservation.
        Deterministic requirements bypass Groq completely.
        """
        from app.services.ai_gateway import ai_gateway as default_gateway

        ai = gateway or default_gateway
        resolved_list: List[NormalizedRequirement] = []

        for req in requirements:
            # Deterministic Bypass: If already normalized or does not require semantic interpretation, do NOT invoke AI
            if req.status == NormalizationStatus.NORMALIZED or not req.requires_semantic_interpretation:
                resolved_list.append(req)
                continue

            # Semantic Escalation via AI Gateway
            try:
                ai_resp = ai.analyze_ambiguous_clause(
                    clause_text=req.source_text,
                    reason_for_escalation=req.ambiguity_reason or "Complex semantic requirement clause",
                    source_page=req.source_page,
                    source_section=req.source_section,
                    candidate_type=req.type,
                    page_start=req.page_start,
                    page_end=req.page_end,
                    section_id=req.section_id,
                    document_id=req.document_id,
                )
                if ai_resp.success and ai_resp.normalized_requirement:
                    resolved_list.append(ai_resp.normalized_requirement)
                else:
                    resolved_list.append(req)
            except Exception as esc_err:
                logger.warning(f"AI Gateway semantic escalation fallback on clause '{req.source_text[:30]}': {esc_err}")
                resolved_list.append(req)

        return resolved_list


tender_requirement_normalizer = TenderRequirementNormalizer()
normalize_clause = tender_requirement_normalizer.normalize_clause
normalize_candidates = tender_requirement_normalizer.normalize_candidates
normalize_sections = tender_requirement_normalizer.normalize_sections
resolve_ambiguous_requirements = tender_requirement_normalizer.resolve_ambiguous_requirements
normalize_indian_currency = tender_requirement_normalizer.normalize_indian_currency
normalize_time_expression = tender_requirement_normalizer.normalize_time_expression
