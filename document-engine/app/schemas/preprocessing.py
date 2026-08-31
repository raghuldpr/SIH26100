from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class PreprocessingConfig(BaseModel):
    """Configuration options for the image preprocessing pipeline."""

    min_dimension: int = Field(
        1500, description="Minimum dimension (max(width, height)) below which image is upscaled"
    )
    enable_grayscale: bool = Field(True, description="Convert color images to single-channel grayscale")
    enable_resize: bool = Field(True, description="Upscale low-resolution images for better OCR quality")
    enable_contrast: bool = Field(True, description="Enhance image contrast")
    adaptive_contrast: bool = Field(
        True, description="Only apply contrast enhancement if standard deviation / dynamic range is low"
    )
    enable_denoise: bool = Field(True, description="Apply noise removal filter")
    adaptive_denoise: bool = Field(
        True, description="Only denoise when high-frequency noise is detected"
    )
    enable_threshold: bool = Field(True, description="Apply binarization / thresholding")
    enable_deskew: bool = Field(True, description="Detect and correct document skew")
    min_skew_angle: float = Field(0.5, description="Minimum skew angle in degrees to trigger rotation")
    max_skew_angle: float = Field(45.0, description="Maximum skew angle in degrees allowed for correction")
    output_format: str = Field("png", description="File format for processed image (png, jpg, tiff)")


class PreprocessingResult(BaseModel):
    """Metadata detailing operations performed during image preprocessing."""

    original_width: int = Field(..., description="Original image width in pixels")
    original_height: int = Field(..., description="Original image height in pixels")
    processed_width: int = Field(..., description="Processed image width in pixels")
    processed_height: int = Field(..., description="Processed image height in pixels")
    operations: List[str] = Field(
        default_factory=list, description="Chronological list of preprocessing operations applied"
    )
    processed_image_path: Optional[str] = Field(
        None, description="Path to the saved processed image in temporary storage"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "original_width": 1200,
                "original_height": 1600,
                "processed_width": 1800,
                "processed_height": 2400,
                "operations": ["grayscale", "resize", "denoise", "threshold"],
                "processed_image_path": "/app/temp/processed/proc_abc123.png",
            }
        }
    )
