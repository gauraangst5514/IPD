"""Validate decoded images before storage; never trust filenames or MIME alone."""
import io
import warnings
from PIL import Image, UnidentifiedImageError
from fastapi import HTTPException

FORMATS = {"JPEG": ("image/jpeg", ".jpg"), "PNG": ("image/png", ".png"), "WEBP": ("image/webp", ".webp")}


def validate_upload(content, content_type, settings):
    if len(content) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Image exceeds byte limit")
    if content_type not in {v[0] for v in FORMATS.values()}:
        raise HTTPException(415, "Unsupported image MIME type")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as image:
                width, height = image.size
                if width * height > settings.MAX_IMAGE_PIXELS:
                    raise HTTPException(413, "Image exceeds pixel limit")
                if image.format not in FORMATS or FORMATS[image.format][0] != content_type:
                    raise HTTPException(415, "Image format does not match MIME type")
                if getattr(image, "n_frames", 1) != 1:
                    raise HTTPException(415, "Animated images are unsupported")
                extension = FORMATS[image.format][1]
                image.verify()
            with Image.open(io.BytesIO(content)) as image:
                image.load()
        return width, height, extension
    except (Image.DecompressionBombWarning, Image.DecompressionBombError):
        raise HTTPException(413, "Image exceeds safe pixel limit")
    except (UnidentifiedImageError, OSError, ValueError):
        raise HTTPException(400, "Invalid image")
