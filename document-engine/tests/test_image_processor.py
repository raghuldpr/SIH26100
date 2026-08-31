import hashlib
from pathlib import Path
import cv2
import numpy as np
import pytest

from app.core.exceptions import (
    CorruptedImageException,
    DocumentNotFoundException,
    UnsupportedImageException,
)
from app.preprocessing.image_processor import ImageProcessor, preprocess_image
from app.schemas.preprocessing import PreprocessingConfig


@pytest.fixture
def create_test_image(tmp_path):
    """Factory fixture for creating synthetic test document images."""

    def _create(
        width: int = 1600,
        height: int = 2000,
        bg_color: int = 255,
        text: str = "BID COMPLIANCE SPECIFICATION - GeM PROCUREMENT",
        rotation_angle: float = 0.0,
        noisy: bool = False,
        low_contrast: bool = False,
        channels: int = 3,
        format: str = "png",
    ) -> Path:
        if channels == 1:
            img = np.full((height, width), bg_color, dtype=np.uint8)
            text_color = 0 if not low_contrast else 180
        else:
            img = np.full((height, width, channels), bg_color, dtype=np.uint8)
            text_color = (0, 0, 0) if not low_contrast else (180, 180, 180)

        # Draw multiple horizontal text lines simulating a document
        for y in range(150, height - 150, 100):
            line_text = f"{text} [Line {y}]"
            cv2.putText(
                img,
                line_text,
                (80, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                text_color,
                2,
                cv2.LINE_AA,
            )

        if noisy:
            # Add salt and pepper noise
            noise = np.random.randint(0, 100, (height, width), dtype=np.uint8)
            noise_mask = noise < 5
            if channels == 1:
                img[noise_mask] = 0
            else:
                img[noise_mask] = (0, 0, 0)

        if rotation_angle != 0.0:
            center = (width // 2, height // 2)
            rot_mat = cv2.getRotationMatrix2D(center, rotation_angle, 1.0)
            img = cv2.warpAffine(
                img,
                rot_mat,
                (width, height),
                flags=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=(255, 255, 255) if channels > 1 else 255,
            )

        path = tmp_path / f"test_img_{width}x{height}_{rotation_angle}deg.{format}"
        # Save image
        ext = f".{format}"
        success, encoded = cv2.imencode(ext, img)
        assert success
        with open(path, "wb") as f:
            f.write(encoded.tobytes())

        return path

    return _create


def test_valid_image_processing(create_test_image, tmp_path):
    """Verify end-to-end preprocessing on a standard document image."""
    img_path = create_test_image(width=1600, height=2000, channels=3)

    result = preprocess_image(img_path)

    assert result.original_width == 1600
    assert result.original_height == 2000
    assert result.processed_width == 1600
    assert result.processed_height == 2000
    assert "grayscale" in result.operations
    assert "threshold" in result.operations
    assert result.processed_image_path is not None

    processed_file = Path(result.processed_image_path)
    assert processed_file.exists()
    assert processed_file.stat().st_size > 0

    # Ensure processed image is readable and binary
    loaded_proc = cv2.imread(str(processed_file), cv2.IMREAD_GRAYSCALE)
    assert loaded_proc is not None
    unique_vals = np.unique(loaded_proc)
    assert len(unique_vals) <= 2  # Binarized with Otsu


def test_low_resolution_image_resizes(create_test_image):
    """Verify small image gets upscaled to meet min_dimension threshold."""
    # 400x500 is well below the 1500 min_dimension threshold
    img_path = create_test_image(width=400, height=500)

    config = PreprocessingConfig(min_dimension=1500)
    result = preprocess_image(img_path, config=config)

    assert "resize" in result.operations
    assert max(result.processed_width, result.processed_height) == 1500
    # Check aspect ratio preservation: 400/500 = 0.8
    assert abs((result.processed_width / result.processed_height) - (400 / 500)) < 0.02


def test_already_good_image_not_overprocessed(create_test_image):
    """Verify clean, high-resolution document is not redundantly resized, contrasted, or denoised."""
    # 1800x2400 high resolution, high contrast (black on pure white), no noise
    img_path = create_test_image(width=1800, height=2400, low_contrast=False, noisy=False)

    config = PreprocessingConfig(min_dimension=1500, adaptive_contrast=True, adaptive_denoise=True)
    result = preprocess_image(img_path, config=config)

    # Resolution is already sufficient, so resize must NOT be executed
    assert "resize" not in result.operations
    # Contrast is already optimal, so adaptive CLAHE must NOT be executed
    assert "contrast" not in result.operations
    # Image has no noise, so adaptive denoise must NOT be executed
    assert "denoise" not in result.operations

    assert result.processed_width == 1800
    assert result.processed_height == 2400


def test_skew_correction(create_test_image):
    """Verify image with noticeable tilt gets deskewed."""
    # Intentionally rotate by 4.0 degrees
    img_path = create_test_image(width=1600, height=2000, rotation_angle=4.0)

    config = PreprocessingConfig(enable_deskew=True, min_skew_angle=0.5, max_skew_angle=45.0)
    result = preprocess_image(img_path, config=config)

    assert "deskew" in result.operations


def test_low_contrast_image_triggers_enhancement(create_test_image):
    """Verify low-contrast/washed-out image triggers contrast enhancement."""
    img_path = create_test_image(width=1600, height=2000, low_contrast=True)

    config = PreprocessingConfig(adaptive_contrast=True)
    result = preprocess_image(img_path, config=config)

    assert "contrast" in result.operations


def test_noisy_image_triggers_denoising(create_test_image):
    """Verify image with noise speckling triggers denoise operation."""
    img_path = create_test_image(width=1600, height=2000, noisy=True)

    config = PreprocessingConfig(adaptive_denoise=True)
    result = preprocess_image(img_path, config=config)

    assert "denoise" in result.operations


def test_invalid_image_non_existent(tmp_path):
    """Verify missing file raises DocumentNotFoundException."""
    missing = tmp_path / "does_not_exist.png"
    with pytest.raises(DocumentNotFoundException) as exc_info:
        preprocess_image(missing)
    assert exc_info.value.code == "DOCUMENT_NOT_FOUND"


def test_invalid_image_empty_file(tmp_path):
    """Verify empty 0-byte image file raises CorruptedImageException."""
    empty_file = tmp_path / "empty.png"
    empty_file.write_bytes(b"")
    with pytest.raises(CorruptedImageException) as exc_info:
        preprocess_image(empty_file)
    assert exc_info.value.code == "CORRUPTED_IMAGE"


def test_invalid_image_corrupted_data(tmp_path):
    """Verify corrupted image bytes raise CorruptedImageException."""
    corrupt_file = tmp_path / "corrupt.png"
    corrupt_file.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRcorruptedcontentjunkdata")
    with pytest.raises(CorruptedImageException) as exc_info:
        preprocess_image(corrupt_file)
    assert exc_info.value.code == "CORRUPTED_IMAGE"


def test_unsupported_image_extension(tmp_path):
    """Verify unsupported file extension raises UnsupportedImageException."""
    unsupported = tmp_path / "document.xyz"
    unsupported.write_bytes(b"data")
    with pytest.raises(UnsupportedImageException) as exc_info:
        preprocess_image(unsupported)
    assert exc_info.value.code == "UNSUPPORTED_IMAGE_FORMAT"


def test_file_immutability(create_test_image):
    """Verify original input image is never modified during preprocessing."""
    img_path = create_test_image(width=1200, height=1500)

    with open(img_path, "rb") as f:
        hash_before = hashlib.sha256(f.read()).hexdigest()
    size_before = img_path.stat().st_size

    _ = preprocess_image(img_path)

    with open(img_path, "rb") as f:
        hash_after = hashlib.sha256(f.read()).hexdigest()
    size_after = img_path.stat().st_size

    assert hash_before == hash_after
    assert size_before == size_after


def test_configurable_pipeline(create_test_image):
    """Verify individual pipeline steps can be toggled via PreprocessingConfig."""
    img_path = create_test_image(width=1600, height=2000)

    # Disable threshold and grayscale
    config = PreprocessingConfig(
        enable_grayscale=False,
        enable_threshold=False,
        enable_contrast=False,
        enable_denoise=False,
        enable_deskew=False,
    )
    result = preprocess_image(img_path, config=config)

    assert "grayscale" not in result.operations
    assert "threshold" not in result.operations
    assert "contrast" not in result.operations
    assert "denoise" not in result.operations
    assert "deskew" not in result.operations
