import logging
from pathlib import Path
from typing import Optional, Union

import pymupdf

logger = logging.getLogger("document_engine.ocr")

# Check for PaddleOCR availability
PADDLE_AVAILABLE = False
try:
    from paddleocr import PaddleOCR
    PADDLE_AVAILABLE = True
except ImportError:
    PADDLE_AVAILABLE = False


class OCREngine:
    """
    OCR Engine supporting PaddleOCR with graceful fallback to PyMuPDF OCR.
    Extracts text from preprocessed document images.
    """

    _paddle_instance = None

    @classmethod
    def get_paddle_ocr(cls):
        """Lazy initialization of PaddleOCR instance."""
        if not PADDLE_AVAILABLE:
            return None
        if cls._paddle_instance is None:
            try:
                cls._paddle_instance = PaddleOCR(use_angle_cls=True, lang="en")
            except Exception as e:
                logger.warning(f"Failed to initialize PaddleOCR: {e}")
                cls._paddle_instance = None
        return cls._paddle_instance

    @classmethod
    def extract_text(cls, image_path: Union[str, Path]) -> str:
        """
        Extracts text from an image file using PaddleOCR if available,
        with fallback to PyMuPDF OCR / image text processing.
        """
        path = Path(image_path).resolve()
        if not path.exists():
            return ""

        # 1. Try PaddleOCR if available
        paddle = cls.get_paddle_ocr()
        if paddle is not None:
            try:
                results = paddle.ocr(str(path), cls=True)
                lines = []
                if results and len(results) > 0 and results[0]:
                    for line in results[0]:
                        if len(line) >= 2 and line[1]:
                            text_str = line[1][0]
                            if text_str:
                                lines.append(text_str.strip())
                if lines:
                    extracted = "\n".join(lines)
                    logger.info(f"PaddleOCR extracted {len(lines)} line(s) from {path.name}")
                    return extracted
            except Exception as e:
                logger.warning(f"PaddleOCR execution error on {path.name}: {e}")

        # 2. PyMuPDF OCR / image text fallback
        try:
            doc = pymupdf.open()
            img = pymupdf.open(str(path))
            rect = img[0].rect
            pdfbytes = img.convert_to_pdf()
            img.close()
            img_pdf = pymupdf.open("pdf", pdfbytes)
            page = doc.new_page(width=rect.width, height=rect.height)
            page.show_pdf_page(rect, img_pdf, 0)
            img_pdf.close()

            # Locate tessdata directory
            tessdata_path = Path(__file__).resolve().parent.parent.parent / "tessdata"
            tessdata_arg = str(tessdata_path) if (tessdata_path / "eng.traineddata").exists() else None

            # Execute built-in OCR textpage
            try:
                if tessdata_arg:
                    tp = page.get_textpage_ocr(language="eng", dpi=300, full=True, tessdata=tessdata_arg)
                else:
                    tp = page.get_textpage_ocr(language="eng", dpi=300, full=True)
                ocr_text = page.get_text("text", textpage=tp)
            except Exception as ocr_err:
                logger.debug(f"PyMuPDF OCR textpage failed, falling back to basic text: {ocr_err}")
                ocr_text = page.get_text("text")

            doc.close()
            return ocr_text.strip()
        except Exception as e:
            logger.warning(f"Fallback OCR error on {path.name}: {e}")
            return ""


def ocr_image(image_path: Union[str, Path]) -> str:
    """Convenience helper for running OCR on an image."""
    return OCREngine.extract_text(image_path)
