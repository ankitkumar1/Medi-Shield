"""OCR text from an uploaded document image or a text-based PDF."""

from functools import lru_cache
from pathlib import Path

import pytesseract
from PIL import Image, ImageOps

Image.MAX_IMAGE_PIXELS = None

for _candidate in ("/opt/homebrew/bin/tesseract", "/usr/local/bin/tesseract"):
    if Path(_candidate).is_file():
        pytesseract.pytesseract.tesseract_cmd = _candidate
        break


def _image(path: Path) -> Image.Image:
    image = Image.open(path).convert("L")
    image = ImageOps.autocontrast(image)
    if image.width < 1600:
        scale = 1600 / image.width
        image = image.resize((int(image.width * scale), int(image.height * scale)))
    elif image.width > 2200:
        scale = 2200 / image.width
        image = image.resize((int(image.width * scale), int(image.height * scale)))
    return image


def blur_variance(path: Path) -> float:
    """High values are sharp. A heavy Gaussian blur drops this sharply."""
    import numpy as np

    image = _image(path)
    image.thumbnail((800, 800))
    arr = np.asarray(image, dtype="float32")
    center = arr[1:-1, 1:-1]
    lap = arr[:-2, 1:-1] + arr[2:, 1:-1] + arr[1:-1, :-2] + arr[1:-1, 2:] - 4 * center
    return float(lap.var())


def _bands(image: Image.Image) -> list[Image.Image]:
    width, height = image.size
    count = 3 if height > 1400 else 1
    if count == 1:
        return [image]
    overlap = int(height * 0.1)
    step = height // count
    crops = []
    for index in range(count):
        top = max(0, index * step - overlap)
        bottom = height if index == count - 1 else (index + 1) * step + overlap
        crops.append(image.crop((0, top, width, bottom)))
    return crops


@lru_cache(maxsize=64)
def read_text(path_str: str) -> str:
    path = Path(path_str)
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    image = _image(path)
    parts = [pytesseract.image_to_string(band, config="--psm 6") for band in _bands(image)]
    return "\n".join(parts)
