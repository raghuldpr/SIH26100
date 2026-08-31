import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from app.classifiers.rules import CLASSIFICATION_RULES, ClassificationRule
from app.extractors.pdf_extractor import PDFExtractor
from app.schemas.classification import ClassificationResult

logger = logging.getLogger("document_engine.classifiers")

# Thresholds for classification confidence
MIN_SCORE_THRESHOLD = 2.0
MIN_CONFIDENCE_THRESHOLD = 0.40
MAX_SINGLE_INDICATOR_CONFIDENCE = 0.65
MAX_POSSIBLE_CONFIDENCE = 0.98


class DocumentClassifier:
    """
    Deterministic document classifier analyzing extracted text with rule-based heuristics,
    keywords, document identifiers, regex patterns, and weighted scoring.
    """

    @classmethod
    def normalize_text(cls, text: str) -> str:
        """
        Normalizes extracted text for reliable keyword and phrase matching:
        - Converts to lowercase
        - Replaces non-breaking spaces and tabs with standard spaces
        - Collapses multiple whitespace characters into single spaces
        """
        if not text:
            return ""
        # Replace non-breaking spaces and other special space characters
        clean = text.replace("\u00a0", " ").replace("\t", " ")
        # Collapse multiple spaces and line breaks into single space
        clean = re.sub(r"\s+", " ", clean).strip().lower()
        return clean

    @classmethod
    def evaluate_rule(
        cls, rule: ClassificationRule, raw_text: str, normalized_text: str
    ) -> Tuple[float, List[str]]:
        """
        Evaluates a single classification rule against the text:
        - Checks strong phrases
        - Checks keywords
        - Evaluates regex patterns against raw and normalized text
        Returns (raw_score, matched_indicators).
        """
        score = 0.0
        matched_indicators: List[str] = []

        # 1. Check strong phrases (high signal)
        for phrase, weight in rule.strong_phrases:
            if phrase.lower() in normalized_text:
                score += weight
                matched_indicators.append(phrase)

        # 2. Check keywords (supporting terminology)
        for kw, weight in rule.keywords:
            pattern = rf"\b{re.escape(kw.lower())}\b"
            if re.search(pattern, normalized_text):
                # Avoid double counting if already captured in a matched strong phrase
                if any(kw.lower() in p.lower() for p in matched_indicators):
                    continue
                score += weight
                matched_indicators.append(kw)

        # 3. Check regex patterns (document numbers, IDs, spaced patterns)
        for regex, indicator_name, weight in rule.patterns:
            # Check against raw text first (for case/format preservation) and normalized
            if regex.search(raw_text) or regex.search(normalized_text):
                score += weight
                matched_indicators.append(indicator_name)

        return score, matched_indicators

    @classmethod
    def calculate_confidence(cls, raw_score: float, match_count: int) -> float:
        """
        Converts raw weight score into a normalized confidence metric [0.00, 0.98]:
        - If only a single indicator matched, caps confidence at MAX_SINGLE_INDICATOR_CONFIDENCE.
        - Scales progressively with multiple corroborating signals.
        - Asymptotically approaches 0.98 but never claims 100% certainty.
        """
        if raw_score <= 0 or match_count == 0:
            return 0.0

        if match_count == 1:
            # Single keyword/indicator cannot exceed 0.65 confidence
            single_conf = 0.30 + min(0.35, (raw_score / 6.0) * 0.35)
            return round(min(MAX_SINGLE_INDICATOR_CONFIDENCE, single_conf), 2)

        # Multi-indicator scoring: scales from 0.60 to 0.98 based on accumulated evidence
        scaled = 0.55 + min(0.43, (raw_score / 12.0) * 0.43)
        return round(min(MAX_POSSIBLE_CONFIDENCE, scaled), 2)

    @classmethod
    def classify_text(cls, text: str) -> ClassificationResult:
        """
        Analyzes extracted text and identifies the most likely document type.
        Returns UNKNOWN if evidence is insufficient or below threshold.
        """
        if not text or not text.strip():
            return ClassificationResult(
                document_type="UNKNOWN",
                confidence=0.0,
                matched_indicators=[],
            )

        raw_text = text
        normalized_text = cls.normalize_text(text)

        best_doc_type = "UNKNOWN"
        best_score = 0.0
        best_indicators: List[str] = []

        for rule in CLASSIFICATION_RULES:
            score, indicators = cls.evaluate_rule(rule, raw_text, normalized_text)
            if score > best_score:
                best_score = score
                best_doc_type = rule.doc_type
                best_indicators = indicators

        # Verify whether the best match meets evidence thresholds
        if best_score < MIN_SCORE_THRESHOLD or not best_indicators:
            return ClassificationResult(
                document_type="UNKNOWN",
                confidence=0.0,
                matched_indicators=[],
            )

        confidence = cls.calculate_confidence(best_score, len(best_indicators))
        if confidence < MIN_CONFIDENCE_THRESHOLD:
            return ClassificationResult(
                document_type="UNKNOWN",
                confidence=0.0,
                matched_indicators=[],
            )

        logger.info(
            f"Classified document as '{best_doc_type}' with confidence {confidence} "
            f"({len(best_indicators)} indicators matched)"
        )

        return ClassificationResult(
            document_type=best_doc_type,
            confidence=confidence,
            matched_indicators=best_indicators,
        )

    @classmethod
    def classify_document(cls, file_path: Union[str, Path]) -> ClassificationResult:
        """
        Extracts text from a document file and classifies its type.
        Supports PDF files via PDFExtractor.
        """
        path = Path(file_path).resolve()
        if path.suffix.lower() == ".pdf":
            extraction = PDFExtractor.extract(path)
            combined_text = "\n".join(p.text for p in extraction.pages)
            return cls.classify_text(combined_text)

        # Fallback for plain text or readable files
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            return cls.classify_text(content)
        except Exception as e:
            logger.error(f"Error reading file for classification {path.name}: {e}")
            return ClassificationResult(
                document_type="UNKNOWN",
                confidence=0.0,
                matched_indicators=[],
            )


def classify_text(text: str) -> ClassificationResult:
    """Convenience helper for classifying text content."""
    return DocumentClassifier.classify_text(text)


def classify_document(file_path: Union[str, Path]) -> ClassificationResult:
    """Convenience helper for classifying a document file."""
    return DocumentClassifier.classify_document(file_path)
