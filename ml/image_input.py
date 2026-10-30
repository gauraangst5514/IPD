"""Decode supported uploads without third-party Image.open monkey patches.

Ultralytics' Pillow patch attempts runtime HEIF installation after any decode
failure. Explicit format decoders keep upload validation offline and bounded.
"""
import io
import warnings
from PIL import Image, JpegImagePlugin, PngImagePlugin, WebPImagePlugin


def open_upload(content):
    if content.startswith(b'\xff\xd8\xff'):
        decoder = JpegImagePlugin.JpegImageFile
    elif content.startswith(b'\x89PNG\r\n\x1a\n'):
        decoder = PngImagePlugin.PngImageFile
    elif content[:4] == b'RIFF' and content[8:12] == b'WEBP':
        decoder = WebPImagePlugin.WebPImageFile
    else:
        raise ValueError('Upload a valid JPEG, PNG or WebP image')
    with warnings.catch_warnings():
        warnings.simplefilter('error', Image.DecompressionBombWarning)
        image = decoder(io.BytesIO(content))
        limit = Image.MAX_IMAGE_PIXELS
        if limit is not None and image.width * image.height > limit:
            image.close()
            raise Image.DecompressionBombError('Image pixel count exceeds upload limit')
        return image
