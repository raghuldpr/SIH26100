import logging
import re
from typing import Any, Dict, List, Optional
from app.schemas.entities import ExtractedEntity

logger = logging.getLogger("app.services.entity_extractor")


class DocumentEntityExtractor:
    """
    Deterministic & RegEx-Powered Entity Extraction Subsystem for SIH-26100.
    Extracts structured key-value entities for all 9 supported document types
    with page localization and confidence estimation.
    """

    @staticmethod
    def _clean_str(val: Optional[str]) -> Optional[str]:
        """Cleans and trims extracted text values, removing trailing punctuation and extra spaces."""
        if not val:
            return None
        cleaned = re.sub(r"\s+", " ", str(val)).strip()
        cleaned = cleaned.rstrip(";,.:-")
        return cleaned if len(cleaned) > 0 else None

    @staticmethod
    def _find_page_number(val: str, pages_text: Optional[List[str]]) -> int:
        """Finds which 1-indexed page contains the target extracted string snippet."""
        if not pages_text or not val:
            return 1
        for idx, p_text in enumerate(pages_text):
            if val.lower() in p_text.lower():
                return idx + 1
        return 1

    def extract_gst_entities(self, text: str, pages: Optional[List[str]] = None) -> Dict[str, ExtractedEntity]:
        """Extracts GSTIN, Legal Name, Registration Status, and Location from GST documents."""
        entities: Dict[str, ExtractedEntity] = {}

        # 1. GSTIN
        gstin_match = re.search(r"\b\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1}\b", text)
        if gstin_match:
            gstin = gstin_match.group(0)
            entities["gstin"] = ExtractedEntity(
                value=gstin,
                confidence=0.99,
                page=self._find_page_number(gstin, pages),
                raw_match=gstin,
            )

        # 2. Company / Legal Name
        name_match = re.search(
            r"(?:Legal Name|Trade Name|Name of Taxable Person)\s*[:\-]?\s*([^\n\r,]+)",
            text,
            re.IGNORECASE,
        )
        if name_match:
            name = self._clean_str(name_match.group(1))
            if name:
                entities["company_name"] = ExtractedEntity(
                    value=name,
                    confidence=0.92,
                    page=self._find_page_number(name, pages),
                    raw_match=name_match.group(0),
                )

        # 3. Registration Status / Taxpayer Type
        type_match = re.search(r"(?:Taxpayer Type|Status)\s*[:\-]?\s*([^\n\r]+)", text, re.IGNORECASE)
        if type_match:
            reg_type = self._clean_str(type_match.group(1))
            if reg_type:
                entities["registration_type"] = ExtractedEntity(
                    value=reg_type,
                    confidence=0.90,
                    page=self._find_page_number(reg_type, pages),
                    raw_match=type_match.group(0),
                )

        # 4. Principal Place of Business
        place_match = re.search(
            r"(?:Principal Place of Business|Address)\s*[:\-]?\s*([^\n\r]+)",
            text,
            re.IGNORECASE,
        )
        if place_match:
            place = self._clean_str(place_match.group(1))
            if place:
                entities["principal_place"] = ExtractedEntity(
                    value=place,
                    confidence=0.88,
                    page=self._find_page_number(place, pages),
                    raw_match=place_match.group(0),
                )

        return entities

    def extract_pan_entities(self, text: str, pages: Optional[List[str]] = None) -> Dict[str, ExtractedEntity]:
        """Extracts PAN Number, Cardholder Name, Father's Name, and Date of Birth."""
        entities: Dict[str, ExtractedEntity] = {}

        # 1. PAN Number
        pan_match = re.search(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", text)
        if pan_match:
            pan = pan_match.group(0)
            entities["pan_number"] = ExtractedEntity(
                value=pan,
                confidence=0.99,
                page=self._find_page_number(pan, pages),
                raw_match=pan,
            )

        # 2. Cardholder Name
        name_match = re.search(
            r"(?:^|\n)\s*Name\s*[:\-]?\s*([A-Za-z\s\.]{3,45})(?:\n|$|\r)",
            text,
            re.IGNORECASE,
        )
        if name_match:
            name = self._clean_str(name_match.group(1))
            if name and not any(kw in name.lower() for kw in ["income tax", "govt", "permanent", "father"]):
                entities["name"] = ExtractedEntity(
                    value=name,
                    confidence=0.92,
                    page=self._find_page_number(name, pages),
                    raw_match=name_match.group(0),
                )

        # 3. Father's Name
        father_match = re.search(
            r"(?:Father's Name|Father Name)\s*[:\-]?\s*([A-Za-z\s\.]{3,45})(?:\n|$|\r)",
            text,
            re.IGNORECASE,
        )
        if father_match:
            father = self._clean_str(father_match.group(1))
            if father:
                entities["father_name"] = ExtractedEntity(
                    value=father,
                    confidence=0.91,
                    page=self._find_page_number(father, pages),
                    raw_match=father_match.group(0),
                )

        # 4. Date of Birth
        dob_match = re.search(
            r"(?:Date of Birth|DOB)\s*[:\-]?\s*(\d{2}[/\-\.]\d{2}[/\-\.]\d{4})",
            text,
            re.IGNORECASE,
        )
        if dob_match:
            dob = dob_match.group(1)
            entities["dob"] = ExtractedEntity(
                value=dob,
                confidence=0.95,
                page=self._find_page_number(dob, pages),
                raw_match=dob_match.group(0),
            )

        return entities

    def extract_udyam_entities(self, text: str, pages: Optional[List[str]] = None) -> Dict[str, ExtractedEntity]:
        """Extracts Udyam Registration Number, Enterprise Name, and Classification."""
        entities: Dict[str, ExtractedEntity] = {}

        # 1. Udyam Number
        udyam_match = re.search(r"\bUDYAM-[A-Z]{2}-\d{2}-\d{7}\b", text)
        if udyam_match:
            udyam_no = udyam_match.group(0)
            entities["udyam_number"] = ExtractedEntity(
                value=udyam_no,
                confidence=0.99,
                page=self._find_page_number(udyam_no, pages),
                raw_match=udyam_no,
            )

        # 2. Enterprise Name
        name_match = re.search(
            r"(?:NAME OF ENTERPRISE|Enterprise Name|Name of Unit\(s\))\s*[:\-]?\s*([^\n\r]+)",
            text,
            re.IGNORECASE,
        )
        if name_match:
            ent_name = self._clean_str(name_match.group(1))
            if ent_name:
                entities["enterprise_name"] = ExtractedEntity(
                    value=ent_name,
                    confidence=0.93,
                    page=self._find_page_number(ent_name, pages),
                    raw_match=name_match.group(0),
                )

        # 3. Enterprise Type (Micro, Small, Medium)
        type_match = re.search(
            r"(?:TYPE OF ENTERPRISE|Enterprise Type|Category)\s*[:\-]?\s*(MICRO|SMALL|MEDIUM)",
            text,
            re.IGNORECASE,
        )
        if type_match:
            ent_type = type_match.group(1).upper()
            entities["enterprise_type"] = ExtractedEntity(
                value=ent_type,
                confidence=0.95,
                page=self._find_page_number(ent_type, pages),
                raw_match=type_match.group(0),
            )

        # 4. Major Activity (Services / Manufacturing)
        act_match = re.search(
            r"(?:MAJOR ACTIVITY|Activity)\s*[:\-]?\s*(SERVICES|MANUFACTURING)",
            text,
            re.IGNORECASE,
        )
        if act_match:
            act = act_match.group(1).upper()
            entities["major_activity"] = ExtractedEntity(
                value=act,
                confidence=0.95,
                page=self._find_page_number(act, pages),
                raw_match=act_match.group(0),
            )

        return entities

    def extract_financial_entities(self, text: str, pages: Optional[List[str]] = None) -> Dict[str, ExtractedEntity]:
        """Extracts Company Name, Financial Year, UDIN, and Annual Turnover."""
        entities: Dict[str, ExtractedEntity] = {}

        # 1. Company Name
        comp_match = re.search(
            r"(?:To the Members of|In respect of|Company Name|Auditor's Report on)\s*[:\-]?\s*([^\n\r,]+)",
            text,
            re.IGNORECASE,
        )
        if comp_match:
            comp_name = self._clean_str(comp_match.group(1))
            if comp_name:
                entities["company_name"] = ExtractedEntity(
                    value=comp_name,
                    confidence=0.90,
                    page=self._find_page_number(comp_name, pages),
                    raw_match=comp_match.group(0),
                )

        # 2. Financial Year
        fy_match = re.search(
            r"(?:for the year ended|Financial Year|ended on)\s*[:\-]?\s*([^\n\r]+)",
            text,
            re.IGNORECASE,
        )
        if fy_match:
            fy = self._clean_str(fy_match.group(1))
            if fy:
                entities["financial_year"] = ExtractedEntity(
                    value=fy,
                    confidence=0.88,
                    page=self._find_page_number(fy, pages),
                    raw_match=fy_match.group(0),
                )

        # 3. UDIN (18 alphanumeric character ICAI verification code)
        udin_match = re.search(r"\bUDIN\s*[:\s]*([A-Za-z0-9]{18})\b", text, re.IGNORECASE)
        if udin_match:
            udin = udin_match.group(1)
            entities["udin"] = ExtractedEntity(
                value=udin,
                confidence=0.98,
                page=self._find_page_number(udin, pages),
                raw_match=udin_match.group(0),
            )


        # 4. Annual Turnover
        turnover_match = re.search(
            r"(?:Annual Turnover|Total Revenue|Turnover)\s*[:\-]?\s*([^\n\r]+)",
            text,
            re.IGNORECASE,
        )
        if turnover_match:
            turnover = self._clean_str(turnover_match.group(1))
            if turnover:
                entities["annual_turnover"] = ExtractedEntity(
                    value=turnover,
                    confidence=0.89,
                    page=self._find_page_number(turnover, pages),
                    raw_match=turnover_match.group(0),
                )

        return entities

    def extract_experience_entities(self, text: str, pages: Optional[List[str]] = None) -> Dict[str, ExtractedEntity]:
        """Extracts Client Organization, Work Description, Contract Value, and Dates."""
        entities: Dict[str, ExtractedEntity] = {}

        # 1. Awarded Vendor / Organization
        vendor_match = re.search(
            r"(?:certify that|issued to|awarded to|Name of Contractor)\s*[:\-]?\s*([^\n\r,]+)",
            text,
            re.IGNORECASE,
        )
        if vendor_match:
            vendor = self._clean_str(vendor_match.group(1))
            if vendor:
                entities["company_name"] = ExtractedEntity(
                    value=vendor,
                    confidence=0.90,
                    page=self._find_page_number(vendor, pages),
                    raw_match=vendor_match.group(0),
                )

        # 2. Scope / Work Description
        work_match = re.search(
            r"(?:execution of work for|for the work of|Scope of Work|Name of Work)\s*[:\-]?\s*([^\n\r]+)",
            text,
            re.IGNORECASE,
        )
        if work_match:
            work = self._clean_str(work_match.group(1))
            if work:
                entities["work_description"] = ExtractedEntity(
                    value=work,
                    confidence=0.88,
                    page=self._find_page_number(work, pages),
                    raw_match=work_match.group(0),
                )

        # 3. Contract Value
        val_match = re.search(
            r"(?:Contract Value|Executed Value|Order Value|Value)\s*[:\-]?\s*([^\n\r]+)",
            text,
            re.IGNORECASE,
        )
        if val_match:
            val = self._clean_str(val_match.group(1))
            if val:
                entities["contract_value"] = ExtractedEntity(
                    value=val,
                    confidence=0.89,
                    page=self._find_page_number(val, pages),
                    raw_match=val_match.group(0),
                )

        # 4. Dates / Completion Date
        date_match = re.search(
            r"(?:completed on|Completion Date|Date of Completion|PO Date)\s*[:\-]?\s*([^\n\r]+)",
            text,
            re.IGNORECASE,
        )
        if date_match:
            dt = self._clean_str(date_match.group(1))
            if dt:
                entities["completion_date"] = ExtractedEntity(
                    value=dt,
                    confidence=0.87,
                    page=self._find_page_number(dt, pages),
                    raw_match=date_match.group(0),
                )

        return entities

    def extract_oem_entities(self, text: str, pages: Optional[List[str]] = None) -> Dict[str, ExtractedEntity]:
        """Extracts OEM Name, Authorized Bidder, and Tender Reference."""
        entities: Dict[str, ExtractedEntity] = {}

        # 1. OEM / Manufacturer Name
        oem_match = re.search(
            r"(?:We,|From:?)\s*([A-Za-z0-9\s,\.\(\)/\-]+?)(?:,\s*who are|do hereby authorize|are official)",
            text,
            re.IGNORECASE,
        )
        if oem_match:
            oem = self._clean_str(oem_match.group(1))
            if oem:
                entities["oem_name"] = ExtractedEntity(
                    value=oem,
                    confidence=0.92,
                    page=self._find_page_number(oem, pages),
                    raw_match=oem_match.group(0),
                )

        # 2. Authorized Bidder
        bidder_match = re.search(
            r"(?:do hereby authorize|authorize)\s*([A-Za-z0-9\s,\.\(\)/\-]+?)\s*(?:to submit|to participate|to bid)",
            text,
            re.IGNORECASE,
        )
        if bidder_match:
            bidder = self._clean_str(bidder_match.group(1))
            if bidder:
                entities["authorized_bidder"] = ExtractedEntity(
                    value=bidder,
                    confidence=0.91,
                    page=self._find_page_number(bidder, pages),
                    raw_match=bidder_match.group(0),
                )

        # 3. Tender Reference
        tender_ref = re.search(
            r"(?:Bid No|Tender Ref|Tender No|Bid Number)\s*[:\-]?\s*([A-Za-z0-9/_\-]+)",
            text,
            re.IGNORECASE,
        )

        if tender_ref:
            t_ref = self._clean_str(tender_ref.group(1))
            if t_ref:
                entities["tender_reference"] = ExtractedEntity(
                    value=t_ref,
                    confidence=0.93,
                    page=self._find_page_number(t_ref, pages),
                    raw_match=tender_ref.group(0),
                )

        return entities

    def extract_mii_entities(self, text: str, pages: Optional[List[str]] = None) -> Dict[str, ExtractedEntity]:
        """Extracts Local Content %, Supplier Class, and Declarant Company Name."""
        entities: Dict[str, ExtractedEntity] = {}

        # 1. Company Name
        comp_match = re.search(
            r"(?:We,|Company Name:?)\s*([A-Za-z0-9\s,\.\(\)]+?)(?:,\s*hereby certify|hereby declare)",
            text,
            re.IGNORECASE,
        )
        if comp_match:
            comp = self._clean_str(comp_match.group(1))
            if comp:
                entities["company_name"] = ExtractedEntity(
                    value=comp,
                    confidence=0.90,
                    page=self._find_page_number(comp, pages),
                    raw_match=comp_match.group(0),
                )

        # 2. Local Content Percentage
        pct_match = re.search(
            r"(?:local content percentage|percentage of local content|local content is)\s*(?:is|of)?\s*[:\-]?\s*(\d+(?:\.\d+)?\s*%?)",
            text,
            re.IGNORECASE,
        )
        if pct_match:
            pct = self._clean_str(pct_match.group(1))
            if pct:
                if not pct.endswith("%"):
                    pct += "%"
                entities["local_content_percentage"] = ExtractedEntity(
                    value=pct,
                    confidence=0.95,
                    page=self._find_page_number(pct, pages),
                    raw_match=pct_match.group(0),
                )

        # 3. Supplier Classification (Class-I, Class-II, Non-Local)
        class_match = re.search(
            r"\b(Class-I Local Supplier|Class-II Local Supplier|Non-Local Supplier)\b",
            text,
            re.IGNORECASE,
        )
        if class_match:
            s_class = class_match.group(1)
            entities["supplier_class"] = ExtractedEntity(
                value=s_class,
                confidence=0.95,
                page=self._find_page_number(s_class, pages),
                raw_match=class_match.group(0),
            )

        return entities

    def extract_tender_entities(self, text: str, pages: Optional[List[str]] = None) -> Dict[str, ExtractedEntity]:
        """Extracts Tender Reference Number, Scope/Title, Organization, and Submission Dates."""
        entities: Dict[str, ExtractedEntity] = {}

        # 1. Tender Reference Number
        gem_match = re.search(r"\b(GEM/\d{4}/[A-Z]/\d+)\b", text)
        if gem_match:
            t_num = gem_match.group(1)
            entities["tender_number"] = ExtractedEntity(
                value=t_num,
                confidence=0.98,
                page=self._find_page_number(t_num, pages),
                raw_match=t_num,
            )
        else:
            nit_match = re.search(
                r"(?:NIT No|Tender No|Bid No|Bid Number)\s*[:\-]?\s*([A-Za-z0-9/_\-]+)",
                text,
                re.IGNORECASE,
            )
            if nit_match:
                t_num = self._clean_str(nit_match.group(1))
                if t_num:
                    entities["tender_number"] = ExtractedEntity(
                        value=t_num,
                        confidence=0.92,
                        page=self._find_page_number(t_num, pages),
                        raw_match=nit_match.group(0),
                    )

        # 2. Scope / Title
        title_match = re.search(
            r"(?:Request for Proposal \(RFP\) for|Tender for|Subject:?)\s*([^\n\r]+)",
            text,
            re.IGNORECASE,
        )
        if title_match:
            title = self._clean_str(title_match.group(1))
            if title:
                entities["title"] = ExtractedEntity(
                    value=title,
                    confidence=0.90,
                    page=self._find_page_number(title, pages),
                    raw_match=title_match.group(0),
                )

        # 3. Organization / Procuring Entity
        org_match = re.search(
            r"(?:Tender Inviting Authority|Procuring Entity|Ministry of|Department of)\s*[:\-]?\s*([^\n\r]+)",
            text,
            re.IGNORECASE,
        )
        if org_match:
            org = self._clean_str(org_match.group(1))
            if org:
                entities["organization"] = ExtractedEntity(
                    value=org,
                    confidence=0.91,
                    page=self._find_page_number(org, pages),
                    raw_match=org_match.group(0),
                )

        # 4. Submission Deadline
        deadline_match = re.search(
            r"(?:Bid Submission Deadline|Bid End Date|Due Date)\s*[:\-]?\s*([^\n\r]+)",
            text,
            re.IGNORECASE,
        )
        if deadline_match:
            dl = self._clean_str(deadline_match.group(1))
            if dl:
                entities["submission_deadline"] = ExtractedEntity(
                    value=dl,
                    confidence=0.90,
                    page=self._find_page_number(dl, pages),
                    raw_match=deadline_match.group(0),
                )

        # 5. EMD Amount
        emd_match = re.search(
            r"(?:EMD Amount|Earnest Money Deposit \(EMD\)|EMD)\s*[:\-]?\s*([^\n\r]+)",
            text,
            re.IGNORECASE,
        )
        if emd_match:
            emd = self._clean_str(emd_match.group(1))
            if emd:
                entities["emd_amount"] = ExtractedEntity(
                    value=emd,
                    confidence=0.92,
                    page=self._find_page_number(emd, pages),
                    raw_match=emd_match.group(0),
                )

        return entities

    def extract(
        self,
        document_type: str,
        text: str,
        pages: Optional[List[str]] = None,
    ) -> Dict[str, ExtractedEntity]:
        """
        Dispatches extraction based on classified document type.
        Returns dictionary of key-value ExtractedEntity objects.
        """
        if not text:
            return {}

        doc_type_upper = (document_type or "").upper()

        if doc_type_upper == "GST":
            return self.extract_gst_entities(text, pages)
        elif doc_type_upper == "PAN":
            return self.extract_pan_entities(text, pages)
        elif doc_type_upper == "UDYAM":
            return self.extract_udyam_entities(text, pages)
        elif doc_type_upper == "FINANCIAL_STATEMENT":
            return self.extract_financial_entities(text, pages)
        elif doc_type_upper == "EXPERIENCE_CERTIFICATE":
            return self.extract_experience_entities(text, pages)
        elif doc_type_upper == "OEM_AUTHORIZATION":
            return self.extract_oem_entities(text, pages)
        elif doc_type_upper == "MII_DECLARATION":
            return self.extract_mii_entities(text, pages)
        elif doc_type_upper in ("TENDER", "TENDER_PDF", "TENDER_NOTICE"):
            return self.extract_tender_entities(text, pages)
        else:
            return {}


# Default singleton instance
entity_extractor = DocumentEntityExtractor()
