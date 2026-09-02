from __future__ import annotations

import logging
from typing import Optional, Tuple

try:
    import cv2
    import fitz  # PyMuPDF
    import numpy as np
except ImportError:
    cv2 = None  # type: ignore
    fitz = None  # type: ignore
    np = None  # type: ignore

logger = logging.getLogger("app.services.image_preprocessor")


class ImagePreprocessor:
    """
    OpenCV Image Preprocessing Engine for Scanned Documents and PDFs.
    Performs resolution normalization, adaptive grayscale conversion, noise reduction,
    contrast enhancement (CLAHE), deskewing / rotation correction, and blank page detection.
    """

    def __init__(
        self,
        max_dimension: int = 2500,
        min_dimension: int = 800,
        enable_clahe: bool = True,
        enable_deskew: bool = True,
    ):
        self.max_dimension = max_dimension
        self.min_dimension = min_dimension
        self.enable_clahe = enable_clahe
        self.enable_deskew = enable_deskew

    @staticmethod
    def bytes_to_cv2(image_bytes: bytes) -> Optional[np.ndarray]:
        """Converts raw image bytes (JPEG, PNG) into an OpenCV BGR numpy array."""
        if not image_bytes:
            return None
        np_arr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        return img

    @staticmethod
    def pdf_page_to_cv2(fitz_page: fitz.Page, dpi: int = 200) -> np.ndarray:
        """
        Renders a PyMuPDF Page directly into an OpenCV BGR numpy array
        at the specified DPI (default 200 DPI for high-accuracy OCR).
        """
        pix = fitz_page.get_pixmap(dpi=dpi)
        # Convert pixmap buffer to numpy array
        img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.height, pix.width, pix.n))

        if pix.n == 4:  # RGBA
            img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGBA2BGR)
        elif pix.n == 3:  # RGB
            img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        elif pix.n == 1:  # Grayscale
            img_bgr = cv2.cvtColor(img_np, cv2.COLOR_GRAY2BGR)
        else:
            img_bgr = img_np

        return img_bgr

    def normalize_resolution(self, image: np.ndarray) -> np.ndarray:
        """
        Normalizes image dimensions. Downscales very large images (> max_dimension)
        to prevent memory exhaustion, and upscales small images for readable text.
        """
        height, width = image.shape[:2]

        if max(height, width) > self.max_dimension:
            scale = self.max_dimension / float(max(height, width))
            new_w = int(width * scale)
            new_h = int(height * scale)
            return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)

        if max(height, width) < self.min_dimension:
            scale = self.min_dimension / float(max(height, width))
            new_w = int(width * scale)
            new_h = int(height * scale)
            return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_CUBIC)

        return image

    @staticmethod
    def is_blank_page(image: np.ndarray, std_threshold: float = 6.0, white_ratio_thresh: float = 0.995) -> bool:
        """
        Detects blank or near-empty pages by analyzing pixel standard deviation
        and background uniformity.
        """
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        std_dev = np.std(gray)
        if std_dev < std_threshold:
            return True

        # Check proportion of pure white pixels
        white_pixels = np.sum(gray > 245)
        total_pixels = gray.size
        if (white_pixels / total_pixels) > white_ratio_thresh:
            return True

        return False

    @staticmethod
    def convert_to_grayscale(image: np.ndarray) -> np.ndarray:
        """Converts BGR image to grayscale if not already single-channel."""
        if len(image.shape) == 3:
            return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        return image

    @staticmethod
    def reduce_noise(gray_image: np.ndarray) -> np.ndarray:
        """Applies gentle bilateral filtering to preserve text edges while removing scan noise."""
        return cv2.bilateralFilter(gray_image, d=5, sigmaColor=50, sigmaSpace=50)

    @staticmethod
    def enhance_contrast(gray_image: np.ndarray) -> np.ndarray:
        """Applies Contrast Limited Adaptive Histogram Equalization (CLAHE) for low-contrast scans."""
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        return clahe.apply(gray_image)

    @staticmethod
    def deskew(gray_image: np.ndarray, max_angle: float = 45.0) -> Tuple[np.ndarray, float]:
        """
        Detects text orientation skew using Otsu thresholding and minimum bounding box,
        rotating the image back to 0 degrees if a skew is detected.
        """
        try:
            # Invert colors: text white, background black
            _, thresh = cv2.threshold(gray_image, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

            # Morphological dilation to connect text characters into lines
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 3))
            dilated = cv2.dilate(thresh, kernel, iterations=1)

            # Find coordinates of all foreground pixels
            pts = np.column_stack(np.where(dilated > 0))
            if len(pts) < 100:
                return gray_image, 0.0

            rect = cv2.minAreaRect(pts)
            angle = rect[-1]

            # Normalize OpenCV minAreaRect angle
            if angle < -45:
                angle = -(90 + angle)
            elif angle > 45:
                angle = 90 - angle
            else:
                angle = -angle

            if abs(angle) < 0.5 or abs(angle) > max_angle:
                return gray_image, 0.0

            # Rotate image with white border padding
            h, w = gray_image.shape[:2]
            center = (w // 2, h // 2)
            rot_mat = cv2.getRotationMatrix2D(center, angle, 1.0)
            rotated = cv2.warpAffine(
                gray_image,
                rot_mat,
                (w, h),
                flags=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=255,
            )
            return rotated, float(round(angle, 2))
        except Exception as exc:
            logger.debug(f"Deskew calculation failed (skipping): {exc}")
            return gray_image, 0.0

    def preprocess(
        self,
        image: np.ndarray,
        apply_deskew: bool = True,
        apply_clahe: bool = True,
    ) -> Tuple[np.ndarray, float, bool]:
        """
        Executes full preprocessing pipeline.
        Returns (preprocessed_image, applied_rotation_angle, is_blank).
        """
        # 1. Normalize resolution
        normalized = self.normalize_resolution(image)

        # 2. Blank page check
        if self.is_blank_page(normalized):
            return normalized, 0.0, True

        # 3. Convert to grayscale
        gray = self.convert_to_grayscale(normalized)

        # 4. Noise reduction
        denoised = self.reduce_noise(gray)

        # 5. Deskew
        rotation_angle = 0.0
        if apply_deskew and self.enable_deskew:
            denoised, rotation_angle = self.deskew(denoised)

        # 6. Contrast enhancement
        if apply_clahe and self.enable_clahe:
            enhanced = self.enhance_contrast(denoised)
        else:
            enhanced = denoised

        return enhanced, rotation_angle, False


# Default singleton instance
image_preprocessor = ImagePreprocessor()
