"""Document classification and type detection modules."""
from app.classifiers.document_classifier import (
    DocumentClassifier,
    classify_document,
    classify_text,
)
from app.classifiers.rules import CLASSIFICATION_RULES, ClassificationRule
from app.schemas.classification import ClassificationResult

__all__ = [
    "DocumentClassifier",
    "ClassificationRule",
    "CLASSIFICATION_RULES",
    "ClassificationResult",
    "classify_text",
    "classify_document",
]

