"""Deterministic, non-AI upload and decoder validation."""

import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from PIL import Image, UnidentifiedImageError

ALLOWED_CONTENT_TYPES: Final[dict[str, str]] = {
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
}


class DeterministicImageValidationError(ValueError):
    """A safe validation rejection with a stable public reason code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.safe_message = message


@dataclass(frozen=True, slots=True)
class ImageValidationLimits:
    """Centralized limits from the formal upload contract and safety ceiling."""

    max_bytes: int
    min_side_px: int
    max_side_px: int
    max_pixels: int


@dataclass(frozen=True, slots=True)
class ValidatedImage:
    """Deterministic metadata extracted from a fully decoded image."""

    detected_format: str
    width: int
    height: int
    pixel_count: int
    color_mode: str
    has_alpha: bool
    exif_orientation: int | None
    validation_details: dict[str, object]


def safe_original_filename(filename: str | None) -> str:
    """Normalize an upload display name without retaining a path."""
    if filename is None:
        return "upload"
    normalized = filename.replace("\\", "/").split("/")[-1].strip()
    normalized = "".join(character for character in normalized if character.isprintable())
    if not normalized:
        return "upload"
    return normalized[:255]


def _signature_format(path: Path) -> str:
    with path.open("rb") as stream:
        header = stream.read(16)
    if len(header) >= 3 and header[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "webp"
    raise DeterministicImageValidationError(
        "rejected_unsupported_format",
        "The file is not an allowed JPEG, PNG, or WebP image.",
    )


def _require_dimensions(
    width: int,
    height: int,
    limits: ImageValidationLimits,
) -> int:
    if width <= 0 or height <= 0:
        raise DeterministicImageValidationError(
            "rejected_dimensions",
            "The decoded image dimensions are invalid.",
        )
    if min(width, height) < limits.min_side_px or max(width, height) > limits.max_side_px:
        raise DeterministicImageValidationError(
            "rejected_dimensions",
            "The image dimensions are outside the allowed range.",
        )
    pixel_count = width * height
    if pixel_count > limits.max_pixels:
        raise DeterministicImageValidationError(
            "rejected_pixel_limit",
            "The image contains more pixels than the safe decoding limit.",
        )
    return pixel_count


def validate_image_file(
    path: Path,
    *,
    declared_content_type: str,
    byte_size: int,
    limits: ImageValidationLimits,
) -> ValidatedImage:
    """Validate signature, MIME, decoder integrity, dimensions, animation, and metadata."""
    if byte_size > limits.max_bytes:
        raise DeterministicImageValidationError(
            "rejected_too_large",
            "The image is larger than the allowed upload limit.",
        )
    signature_format = _signature_format(path)
    expected_content_type = ALLOWED_CONTENT_TYPES[signature_format]
    if declared_content_type != expected_content_type:
        raise DeterministicImageValidationError(
            "rejected_content_type_mismatch",
            "The declared content type does not match the image bytes.",
        )

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as image:
                detected_format = (image.format or "").lower()
                if detected_format == "jpg":
                    detected_format = "jpeg"
                if detected_format != signature_format:
                    raise DeterministicImageValidationError(
                        "rejected_content_type_mismatch",
                        "The decoder format does not match the image signature.",
                    )
                if (
                    bool(getattr(image, "is_animated", False))
                    or int(getattr(image, "n_frames", 1)) != 1
                ):
                    raise DeterministicImageValidationError(
                        "rejected_unsupported_format",
                        "Animated images are not supported.",
                    )
                pixel_count = _require_dimensions(image.width, image.height, limits)
                image.verify()

            with Image.open(path) as decoded:
                if decoded.size != (image.width, image.height):
                    raise DeterministicImageValidationError(
                        "rejected_corrupt",
                        "The image dimensions changed during decoding.",
                    )
                decoded.load()
                color_mode = decoded.mode[:32]
                has_alpha = "A" in decoded.getbands() or (
                    decoded.mode == "P" and "transparency" in decoded.info
                )
                orientation_value = decoded.getexif().get(274)
                exif_orientation = (
                    int(orientation_value)
                    if isinstance(orientation_value, int) and 1 <= orientation_value <= 8
                    else None
                )
    except DeterministicImageValidationError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise DeterministicImageValidationError(
            "rejected_pixel_limit",
            "The image exceeds the safe decoding limit.",
        ) from None
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
        raise DeterministicImageValidationError(
            "rejected_corrupt",
            "The image could not be decoded completely.",
        ) from None

    return ValidatedImage(
        detected_format=signature_format,
        width=image.width,
        height=image.height,
        pixel_count=pixel_count,
        color_mode=color_mode,
        has_alpha=has_alpha,
        exif_orientation=exif_orientation,
        validation_details={
            "validation_contract": "phase_1e_1_upload_validation.v1",
            "signature_verified": True,
            "declared_content_type_verified": True,
            "decoder_verified": True,
            "fully_decoded": True,
            "animated": False,
        },
    )
