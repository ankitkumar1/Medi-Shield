"""TrueType lookup for the document painters. Falls back to the default bitmap font."""

import os

from PIL import ImageFont

SUPPLEMENTAL = "/System/Library/Fonts/Supplemental"
LIBRARY = "/Library/Fonts"
WINDOWS = r"C:\Windows\Fonts"

FILE_MAP = {
    "arial.ttf": "Arial.ttf",
    "arialbd.ttf": "Arial Bold.ttf",
    "ariali.ttf": "Arial Italic.ttf",
    "cour.ttf": "Courier New.ttf",
}

SIGNATURES = [
    os.path.join(SUPPLEMENTAL, "Bradley Hand Bold.ttf"),
    os.path.join(SUPPLEMENTAL, "Brush Script.ttf"),
    os.path.join(WINDOWS, "segoesc.ttf"),
    os.path.join(WINDOWS, "BRADHITC.TTF"),
]


def fnt(name, size):
    mapped = FILE_MAP.get(name, name)
    candidates = [
        name,
        mapped,
        os.path.join(SUPPLEMENTAL, mapped),
        os.path.join(LIBRARY, mapped),
        os.path.join(WINDOWS, name),
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def signature_fnt(size):
    for path in SIGNATURES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return fnt("ariali.ttf", size)
