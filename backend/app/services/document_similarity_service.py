"""
Document Similarity and Duplicate Detection Service (Phase 22.8)

Provides deterministic, local-first similarity and duplicate detection
across extracted document text and cryptographic hashes.

Guarantees:
1. Deterministic: identical inputs produce identical outputs.
2. Local-first: zero external LLM/AI API calls, zero embeddings, zero vector DB.
3. Neutral terminology: reports objective similarity; never generates accusations of
   plagiarism, fraud, or forgery.
4. Non-altering: does not modify procurement qualification decisions, compliance policy,
   risk scoring, or confidence.
"""
from typing import Any, Dict, List, Optional, Set, Tuple
import re
import logging

from app.schemas.verification import (
    DocumentReference,
    DocumentSimilarityComparison,
    VerificationDocumentSimilarity,
)

logger = logging.getLogger("app.services.document_similarity")

# -----------------------------------------------------------------------------
# Documented Deterministic Similarity Thresholds
# -----------------------------------------------------------------------------
# EXACT_DUPLICATE: Identical SHA-256 digest or 100% token/content identity
SIMILARITY_THRESHOLD_EXACT: float = 1.0

# HIGH_SIMILARITY: >= 80% Jaccard token similarity; indicates near-identical
# phrasing, boilerplate reuse, or minor modifications.
SIMILARITY_THRESHOLD_HIGH: float = 0.80

# MODERATE_SIMILARITY: >= 50% and < 80% Jaccard token similarity; indicates
# substantial shared content or overlapping structural sections.
SIMILARITY_THRESHOLD_MODERATE: float = 0.50

# Below 0.50 is classified as LOW_SIMILARITY.


def normalize_text(text: Optional[str]) -> str:
    """
    Deterministically normalizes text:
    - Lowercases
    - Strips non-alphanumeric noise (retaining alphanumeric chars and spaces)
    - Collapses multiple whitespace/newlines into a single space
    - Strips leading and trailing whitespace
    """
    if not text:
        return ""
    # Lowercase
    cleaned = text.lower()
    # Replace non-alphanumeric characters with spaces
    cleaned = re.sub(r"[^\w\s]", " ", cleaned, flags=re.UNICODE)
    # Collapse consecutive whitespace characters into a single space
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def tokenize_text(text: Optional[str]) -> Set[str]:
    """
    Deterministically extracts unique word tokens from normalized text.
    """
    normalized = normalize_text(text)
    if not normalized:
        return set()
    return set(normalized.split())


def calculate_jaccard_similarity(tokens_a: Set[str], tokens_b: Set[str]) -> float:
    """
    Calculates deterministic Jaccard token similarity:
    J(A, B) = |A ∩ B| / |A ∪ B|
    Returns a float between 0.0 and 1.0 rounded to 4 decimal places.
    """
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = len(tokens_a & tokens_b)
    union = len(tokens_a | tokens_b)
    if union == 0:
        return 0.0
    return round(intersection / union, 4)


class DocumentSimilarityService:
    """
    Deterministic document similarity analyzer operating on existing
    extracted document texts and cryptographic hashes.
    """

    def analyze_similarity(
        self,
        payload: Optional[Any] = None,
        documents: Optional[List[Any]] = None,
        bidder_evidence: Optional[List[Any]] = None,
    ) -> VerificationDocumentSimilarity:
        """
        Analyzes submitted documents for exact duplicates and content similarity.
        """
        # 1. Harvest document descriptors
        doc_records = self._extract_document_records(
            payload=payload,
            documents=documents,
            bidder_evidence=bidder_evidence,
        )

        # 2. Check reference corpus availability
        if len(doc_records) < 2:
            return VerificationDocumentSimilarity(
                overall_status="INSUFFICIENT_REFERENCE_CORPUS",
                comparisons=[],
                reason="Similarity analysis requires at least two comparable documents or an available reference corpus.",
            )

        # Check if all documents have empty text and distinct/missing hashes
        all_empty_text = all(not d["tokens"] for d in doc_records)
        all_hashes = [d["sha256"] for d in doc_records if d["sha256"]]
        has_hash_collision = len(all_hashes) != len(set(all_hashes))

        if all_empty_text and not has_hash_collision:
            return VerificationDocumentSimilarity(
                overall_status="INSUFFICIENT_REFERENCE_CORPUS",
                comparisons=[],
                reason="Extracted document text is insufficient for similarity comparison.",
            )

        # 3. Pairwise deterministic comparison
        comparisons: List[DocumentSimilarityComparison] = []
        comp_index = 1

        for i in range(len(doc_records)):
            for j in range(i + 1, len(doc_records)):
                doc_a = doc_records[i]
                doc_b = doc_records[j]

                comp = self._compare_document_pair(
                    comp_id=f"SIM-{comp_index:03d}",
                    doc_a=doc_a,
                    doc_b=doc_b,
                )
                if comp:
                    comparisons.append(comp)
                    comp_index += 1

        if not comparisons:
            return VerificationDocumentSimilarity(
                overall_status="INSUFFICIENT_REFERENCE_CORPUS",
                comparisons=[],
                reason="Similarity analysis requires at least two comparable documents or an available reference corpus.",
            )

        # 4. Determine overall status
        overall_status = self._derive_overall_status(comparisons)

        return VerificationDocumentSimilarity(
            overall_status=overall_status,
            comparisons=comparisons,
            reason=self._derive_overall_reason(overall_status, comparisons),
        )

    def _extract_document_records(
        self,
        payload: Optional[Any] = None,
        documents: Optional[List[Any]] = None,
        bidder_evidence: Optional[List[Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Extracts unified document records containing document_id, source_document,
        sha256, normalized text, tokens, and page-level text.
        """
        docs_raw = list(documents) if documents else []
        if not docs_raw and payload and hasattr(payload, "documents") and payload.documents:
            docs_raw = list(payload.documents)

        evidences_raw = list(bidder_evidence) if bidder_evidence else []
        if not evidences_raw and payload and hasattr(payload, "bidder_evidence") and payload.bidder_evidence:
            evidences_raw = list(payload.bidder_evidence)

        doc_dict: Dict[str, Dict[str, Any]] = {}

        # First populate from documents list
        for doc in docs_raw:
            d_id = getattr(doc, "document_id", None) or (doc.get("document_id") if isinstance(doc, dict) else None)
            f_name = (
                getattr(doc, "file_name", None)
                or getattr(doc, "source_document", None)
                or (doc.get("file_name") if isinstance(doc, dict) else None)
                or (doc.get("source_document") if isinstance(doc, dict) else None)
                or "submitted_document.pdf"
            )
            key = str(d_id) if d_id else f_name
            sha = getattr(doc, "sha256", None) or (doc.get("sha256") if isinstance(doc, dict) else None)
            
            # Extract full text
            ocr_text = getattr(doc, "ocr_text", None) or (doc.get("ocr_text") if isinstance(doc, dict) else None)
            ext_data = getattr(doc, "extracted_data", None) or (doc.get("extracted_data") if isinstance(doc, dict) else {}) or {}
            
            raw_text = (
                ocr_text
                or ext_data.get("raw_text")
                or ext_data.get("ocr_text")
                or ext_data.get("text")
                or ""
            )

            # Extract page-level text if available
            pages_dict: Dict[int, str] = {}
            if isinstance(ext_data, dict):
                pages_data = ext_data.get("pages")
                if isinstance(pages_data, list):
                    for p in pages_data:
                        if isinstance(p, dict):
                            p_num = p.get("page_number") or p.get("page")
                            p_txt = p.get("text") or ""
                            if p_num is not None and p_txt:
                                pages_dict[int(p_num)] = p_txt
                
                # Also check entities if pages not directly present
                if not pages_dict and "entities" in ext_data and isinstance(ext_data["entities"], dict):
                    for ent_name, ent_val in ext_data["entities"].items():
                        if isinstance(ent_val, dict):
                            p_num = ent_val.get("page")
                            p_raw = ent_val.get("raw_match") or ent_val.get("value")
                            if p_num is not None and p_raw:
                                pages_dict.setdefault(int(p_num), "")
                                pages_dict[int(p_num)] += " " + str(p_raw)

            if not raw_text and pages_dict:
                raw_text = " ".join(pages_dict.values())

            doc_dict[key] = {
                "document_id": str(d_id) if d_id else None,
                "source_document": f_name,
                "sha256": sha.strip().lower() if sha and isinstance(sha, str) else None,
                "raw_text": raw_text,
                "normalized_text": normalize_text(raw_text),
                "tokens": tokenize_text(raw_text),
                "pages": pages_dict,
            }

        # Complement or populate from bidder_evidence
        for ev in evidences_raw:
            d_id = getattr(ev, "document_id", None) or (ev.get("document_id") if isinstance(ev, dict) else None)
            f_name = (
                getattr(ev, "source_document", None)
                or (ev.get("source_document") if isinstance(ev, dict) else None)
            )
            if not d_id and not f_name:
                continue

            key = str(d_id) if d_id else f_name
            sha = (
                getattr(ev, "document_hash", None)
                or (ev.get("document_hash") if isinstance(ev, dict) else None)
            )
            p_num = (
                getattr(ev, "page_number", None)
                or getattr(ev, "source_page", None)
                or (ev.get("page_number") if isinstance(ev, dict) else None)
                or (ev.get("source_page") if isinstance(ev, dict) else None)
            )
            src_txt = (
                getattr(ev, "source_text", None)
                or getattr(ev, "text_snippet", None)
                or (ev.get("source_text") if isinstance(ev, dict) else None)
                or (ev.get("text_snippet") if isinstance(ev, dict) else None)
                or ""
            )

            if key not in doc_dict:
                doc_dict[key] = {
                    "document_id": str(d_id) if d_id else None,
                    "source_document": f_name or f"doc_{d_id}.pdf",
                    "sha256": sha.strip().lower() if sha and isinstance(sha, str) else None,
                    "raw_text": src_txt,
                    "normalized_text": normalize_text(src_txt),
                    "tokens": tokenize_text(src_txt),
                    "pages": {int(p_num): src_txt} if p_num is not None and src_txt else {},
                }
            else:
                existing = doc_dict[key]
                if not existing["sha256"] and sha:
                    existing["sha256"] = sha.strip().lower()
                if src_txt:
                    if not existing["raw_text"]:
                        existing["raw_text"] = src_txt
                        existing["normalized_text"] = normalize_text(src_txt)
                        existing["tokens"] = tokenize_text(src_txt)
                    else:
                        existing["raw_text"] += " " + src_txt
                        existing["normalized_text"] = normalize_text(existing["raw_text"])
                        existing["tokens"] = tokenize_text(existing["raw_text"])
                if p_num is not None and src_txt:
                    existing["pages"][int(p_num)] = existing["pages"].get(int(p_num), "") + " " + src_txt

        return list(doc_dict.values())

    def _compare_document_pair(
        self,
        comp_id: str,
        doc_a: Dict[str, Any],
        doc_b: Dict[str, Any],
    ) -> Optional[DocumentSimilarityComparison]:
        """
        Deterministically compares two documents.
        Checks SHA-256 equality first; falls back to Jaccard token similarity over normalized text.
        Preserves page-level numbers if available; leaves them None if absent.
        """
        ref_a = DocumentReference(
            document_id=doc_a.get("document_id"),
            source_document=doc_a.get("source_document"),
            page_number=None,
        )
        ref_b = DocumentReference(
            document_id=doc_b.get("document_id"),
            source_document=doc_b.get("source_document"),
            page_number=None,
        )

        sha_a = doc_a.get("sha256")
        sha_b = doc_b.get("sha256")

        # 1. Exact duplicate via identical cryptographic hash
        if sha_a and sha_b and sha_a == sha_b:
            return DocumentSimilarityComparison(
                comparison_id=comp_id,
                document_a=ref_a,
                document_b=ref_b,
                document_a_page=None,
                document_b_page=None,
                comparison_type="EXACT_DUPLICATE",
                similarity_score=SIMILARITY_THRESHOLD_EXACT,
                threshold=SIMILARITY_THRESHOLD_EXACT,
                status="EXACT_DUPLICATE",
                reason="Documents have identical SHA-256 content.",
            )

        # 2. Content similarity using normalized text and token Jaccard similarity
        norm_a = doc_a.get("normalized_text", "")
        norm_b = doc_b.get("normalized_text", "")
        tokens_a = doc_a.get("tokens", set())
        tokens_b = doc_b.get("tokens", set())

        # If both are empty and no hash match, cannot compare content
        if not tokens_a and not tokens_b:
            return None

        # Check for identical normalized text
        if norm_a and norm_b and norm_a == norm_b:
            # Different hashes but identical normalized text
            p_a, p_b = self._find_matching_pages(doc_a.get("pages", {}), doc_b.get("pages", {}))
            ref_a.page_number = p_a
            ref_b.page_number = p_b

            return DocumentSimilarityComparison(
                comparison_id=comp_id,
                document_a=ref_a,
                document_b=ref_b,
                document_a_page=p_a,
                document_b_page=p_b,
                comparison_type="CONTENT_SIMILARITY",
                similarity_score=1.0,
                threshold=SIMILARITY_THRESHOLD_HIGH,
                status="HIGH_SIMILARITY",
                reason="Documents contain identical normalized text.",
            )

        similarity_score = calculate_jaccard_similarity(tokens_a, tokens_b)

        # Determine page-level evidence if page text is present
        p_a, p_b = self._find_matching_pages(doc_a.get("pages", {}), doc_b.get("pages", {}))
        ref_a.page_number = p_a
        ref_b.page_number = p_b

        if similarity_score >= SIMILARITY_THRESHOLD_HIGH:
            status = "HIGH_SIMILARITY"
            threshold = SIMILARITY_THRESHOLD_HIGH
            reason = "Documents contain highly similar normalized text."
        elif similarity_score >= SIMILARITY_THRESHOLD_MODERATE:
            status = "MODERATE_SIMILARITY"
            threshold = SIMILARITY_THRESHOLD_MODERATE
            reason = "Documents contain moderately similar content."
        else:
            status = "LOW_SIMILARITY"
            threshold = SIMILARITY_THRESHOLD_MODERATE
            reason = "Documents have low content similarity."

        return DocumentSimilarityComparison(
            comparison_id=comp_id,
            document_a=ref_a,
            document_b=ref_b,
            document_a_page=p_a,
            document_b_page=p_b,
            comparison_type="CONTENT_SIMILARITY",
            similarity_score=similarity_score,
            threshold=threshold,
            status=status,
            reason=reason,
        )

    def _find_matching_pages(
        self,
        pages_a: Dict[int, str],
        pages_b: Dict[int, str],
    ) -> Tuple[Optional[int], Optional[int]]:
        """
        Determines the page numbers with the highest text similarity if page-level
        information is available. Returns (None, None) if page text is not available.
        """
        if not pages_a or not pages_b:
            return None, None

        best_score = -1.0
        best_pa: Optional[int] = None
        best_pb: Optional[int] = None

        for pa, text_a in pages_a.items():
            tok_a = tokenize_text(text_a)
            if not tok_a:
                continue
            for pb, text_b in pages_b.items():
                tok_b = tokenize_text(text_b)
                if not tok_b:
                    continue
                score = calculate_jaccard_similarity(tok_a, tok_b)
                if score > best_score:
                    best_score = score
                    best_pa = pa
                    best_pb = pb

        if best_score >= SIMILARITY_THRESHOLD_MODERATE:
            return best_pa, best_pb
        return None, None

    def _derive_overall_status(
        self,
        comparisons: List[DocumentSimilarityComparison],
    ) -> str:
        """
        Derives canonical overall_status:
        - EXACT_DUPLICATE: if at least one comparison is EXACT_DUPLICATE
        - SIMILARITY_FOUND: if at least one comparison is HIGH_SIMILARITY or MODERATE_SIMILARITY
        - NO_COMPARISON: if all comparisons are LOW_SIMILARITY
        """
        if any(c.status == "EXACT_DUPLICATE" for c in comparisons):
            return "EXACT_DUPLICATE"
        if any(c.status in ("HIGH_SIMILARITY", "MODERATE_SIMILARITY") for c in comparisons):
            return "SIMILARITY_FOUND"
        return "NO_COMPARISON"

    def _derive_overall_reason(
        self,
        overall_status: str,
        comparisons: List[DocumentSimilarityComparison],
    ) -> str:
        """
        Generates neutral, descriptive summary reason.
        """
        if overall_status == "EXACT_DUPLICATE":
            return "Exact duplicate document content detected based on cryptographic hash equality."
        if overall_status == "SIMILARITY_FOUND":
            high_count = sum(1 for c in comparisons if c.status == "HIGH_SIMILARITY")
            mod_count = sum(1 for c in comparisons if c.status == "MODERATE_SIMILARITY")
            return f"Content similarity detected ({high_count} high, {mod_count} moderate)."
        if overall_status == "NO_COMPARISON":
            return "No significant document similarity or duplicate content detected."
        return "Similarity analysis requires at least two comparable documents or an available reference corpus."


document_similarity_service = DocumentSimilarityService()
