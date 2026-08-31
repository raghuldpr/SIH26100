import logging
import uuid
from pathlib import Path
from typing import List, Optional, Tuple, Union

import cv2
import numpy as np

from app.core.config import settings
from app.core.exceptions import (
    CorruptedImageException,
    DocumentNotFoundException,
    UnsupportedImageException,
)
from app.schemas.preprocessing import PreprocessingConfig, PreprocessingResult

logger = logging.getLogger("document_engine.preprocessing")

SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"}


class ImageProcessor:
    """
    Modular and configurable image preprocessing engine for OCR optimization.
    Implements safe loading, resolution upscaling, adaptive contrast/denoise,
    Otsu thresholding, and document skew correction.
    """

    @classmethod
    def load_image(cls, file_path: Union[str, Path]) -> np.ndarray:
        """
        Safely loads an image from filesystem using binary buffer decoding.
        Supports cross-platform and Windows non-ASCII paths.
        """
        path = Path(file_path).resolve()

        if not path.exists():
            raise DocumentNotFoundException(message=f"Image file not found: {path.name}")

        if not path.is_file():
            raise UnsupportedImageException(message=f"Path is not a regular file: {path.name}")

        if path.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
            raise UnsupportedImageException(
                message=f"Unsupported image extension '{path.suffix}'. Supported: {SUPPORTED_IMAGE_EXTENSIONS}"
            )

        if path.stat().st_size == 0:
            raise CorruptedImageException(message=f"Image file is empty (0 bytes): {path.name}")

        try:
            with open(path, "rb") as f:
                buffer = f.read()
            arr = np.frombuffer(buffer, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        except Exception as e:
            logger.error(f"Failed to read image buffer for {path.name}: {e}")
            raise CorruptedImageException(
                message=f"Unable to read image bytes: {path.name}", details=str(e)
            )

        if img is None or img.size == 0 or img.shape[0] == 0 or img.shape[1] == 0:
            raise CorruptedImageException(
                message=f"Image file could not be decoded or is corrupted: {path.name}"
            )

        return img

    @classmethod
    def to_grayscale(cls, img: np.ndarray) -> Tuple[np.ndarray, bool]:
        """Converts color image to single-channel grayscale if not already grayscale."""
        if len(img.shape) == 2:
            return img, False

        if img.shape[2] == 4:
            gray = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
            return gray, True

        if img.shape[2] == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            return gray, True

        return img, False

    @classmethod
    def resize_low_resolution(
        cls, img: np.ndarray, min_dimension: int = 1500
    ) -> Tuple[np.ndarray, bool]:
        """
        Upscales low-resolution images so the largest dimension meets the min_dimension threshold.
        Does not downscale or over-process images that are already high resolution.
        """
        h, w = img.shape[:2]
        max_dim = max(h, w)

        if max_dim < min_dimension:
            scale = min_dimension / float(max_dim)
            new_w = int(round(w * scale))
            new_h = int(round(h * scale))
            resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
            return resized, True

        return img, False

    @classmethod
    def enhance_contrast(
        cls, img: np.ndarray, adaptive: bool = True, clip_limit: float = 2.0
    ) -> Tuple[np.ndarray, bool]:
        """
        Improves image contrast using CLAHE (Contrast Limited Adaptive Histogram Equalization).
        If adaptive is True, only applies CLAHE when dynamic range or standard deviation is low.
        """
        if adaptive:
            std_dev = float(np.std(img))
            dynamic_range = float(np.ptp(img))  # max - min
            # Skip already well-contrasted images (e.g. sharp black text on white paper)
            if std_dev >= 45.0 and dynamic_range >= 180.0:
                return img, False

        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
        enhanced = clahe.apply(img)
        return enhanced, True

    @classmethod
    def remove_noise(cls, img: np.ndarray, adaptive: bool = True) -> Tuple[np.ndarray, bool]:
        """
        Removes salt-and-pepper and sensor noise using median filtering.
        In adaptive mode, estimates noise variance and skips clean images.
        """
        if adaptive:
            # Estimate noise variance using Laplacian
            lap = cv2.Laplacian(img, cv2.CV_64F)
            variance = float(lap.var())
            # Very low or very high variance indicates noise or background speckling
            # If standard deviation of flat areas is clean, skip
            # High-frequency noise check: compare blurred difference
            diff = cv2.absdiff(img, cv2.medianBlur(img, 3))
            noise_ratio = float(np.mean(diff > 15))
            if noise_ratio < 0.015:
                return img, False

        denoised = cv2.medianBlur(img, 3)
        return denoised, True

    @classmethod
    def apply_threshold(cls, img: np.ndarray) -> Tuple[np.ndarray, bool]:
        """
        Applies Otsu's automatic thresholding to create crisp binarized text.
        Ensures standard document convention: black text on white background.
        """
        # Apply Otsu binarization
        _, thresh = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Ensure background is white (255)
        white_pixels = np.sum(thresh == 255)
        total_pixels = thresh.size
        if white_pixels < (total_pixels * 0.5):
            thresh = cv2.bitwise_not(thresh)

        return thresh, True

    @classmethod
    def correct_skew(
        cls,
        img: np.ndarray,
        min_angle: float = 0.5,
        max_angle: float = 45.0,
    ) -> Tuple[np.ndarray, bool]:
        """
        Detects text line orientation and deskews document if within the valid angle range.
        Uses white padding so rotated borders do not interfere with OCR.
        """
        # Determine foreground (text) coordinates
        # Text is black (0) on white (255), so invert for coordinate analysis
        inv = 255 - img if len(img.shape) == 2 else 255 - cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        coords = np.column_stack(np.where(inv > 50))

        if len(coords) < 100:
            return img, False

        rect = cv2.minAreaRect(coords)
        angle = rect[-1]

        # Normalize angle convention
        if angle < -45.0:
            angle = -(90.0 + angle)
        elif angle > 45.0:
            angle = 90.0 - angle
        else:
            angle = -angle

        # Only correct if skew is noticeable and realistic for a document
        if min_angle <= abs(angle) <= max_angle:
            h, w = img.shape[:2]
            center = (w // 2, h // 2)
            rot_mat = cv2.getRotationMatrix2D(center, angle, 1.0)
            rotated = cv2.warpAffine(
                img,
                rot_mat,
                (w, h),
                flags=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=255,
            )
            logger.info(f"Deskewed image by {angle:.2f} degrees")
            return rotated, True

        return img, False

    @classmethod
    def save_processed_image(
        cls,
        img: np.ndarray,
        output_dir: Optional[Path] = None,
        output_format: str = "png",
    ) -> str:
        """
        Safely saves processed image buffer to the temporary processed artifacts directory.
        Never overwrites or modifies source files.
        """
        target_dir = output_dir or (settings.temp_path / "processed")
        target_dir.mkdir(parents=True, exist_ok=True)

        filename = f"proc_{uuid.uuid4().hex}.{output_format}"
        target_file = target_dir / filename

        ext = f".{output_format}"
        success, encoded = cv2.imencode(ext, img)
        if not success:
            raise CorruptedImageException(
                message=f"Failed to encode processed image to format '{output_format}'"
            )

        with open(target_file, "wb") as f:
            f.write(encoded.tobytes())

        return str(target_file.resolve())

    @classmethod
    def process(
        cls,
        file_path: Union[str, Path],
        config: Optional[PreprocessingConfig] = None,
        output_dir: Optional[Path] = None,
    ) -> PreprocessingResult:
        """
        Executes the configured preprocessing pipeline on an input image.
        Returns detailed metadata and the path to the processed artifact.
        """
        cfg = config or PreprocessingConfig()
        img = cls.load_image(file_path)

        orig_h, orig_w = img.shape[:2]
        operations_applied: List[str] = []
        current = img

        # 1. Grayscale conversion
        if cfg.enable_grayscale:
            current, applied = cls.to_grayscale(current)
            if applied:
                operations_applied.append("grayscale")

        # 2. Resize low-resolution images
        if cfg.enable_resize:
            current, applied = cls.resize_low_resolution(current, min_dimension=cfg.min_dimension)
            if applied:
                operations_applied.append("resize")

        # 3. Contrast enhancement (adaptive or explicit)
        if cfg.enable_contrast:
            current, applied = cls.enhance_contrast(current, adaptive=cfg.adaptive_contrast)
            if applied:
                operations_applied.append("contrast")

        # 4. Noise removal (adaptive or explicit)
        if cfg.enable_denoise:
            current, applied = cls.remove_noise(current, adaptive=cfg.adaptive_denoise)
            if applied:
                operations_applied.append("denoise")

        # 5. Skew correction before thresholding
        if cfg.enable_deskew:
            current, applied = cls.correct_skew(
                current, min_angle=cfg.min_skew_angle, max_angle=cfg.max_skew_angle
            )
            if applied:
                operations_applied.append("deskew")

        # 6. Thresholding / binarization
        if cfg.enable_threshold:
            current, applied = cls.apply_threshold(current)
            if applied:
                operations_applied.append("threshold")

        proc_h, proc_w = current.shape[:2]

        # Save to temporary processed directory
        saved_path = cls.save_processed_image(
            current, output_dir=output_dir, output_format=cfg.output_format
        )

        return PreprocessingResult(
            original_width=orig_w,
            original_height=orig_h,
            processed_width=proc_w,
            processed_height=proc_h,
            operations=operations_applied,
            processed_image_path=saved_path,
        )


def preprocess_image(
    file_path: Union[str, Path],
    config: Optional[PreprocessingConfig] = None,
    output_dir: Optional[Path] = None,
) -> PreprocessingResult:
    """Convenience helper for image preprocessing."""
    return ImageProcessor.process(file_path, config=config, output_dir=output_dir)
