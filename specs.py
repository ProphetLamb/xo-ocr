import glob
from pathlib import Path
import re
import cv2
from ocr import crop_box_extraction_gray, crop_by_spec, ocr_image
import typing as t
from skimage.metrics import structural_similarity as ssim


def _image_similarity(img1: cv2.typing.MatLike, img2: cv2.typing.MatLike):
    """
    Computes SSIM similarity score between two images.
    Score range: -1 to 1 (1 = identical).
    """

    # Convert to grayscale
    gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
    gray1 = crop_box_extraction_gray(gray1, color=255)
    gray2 = crop_box_extraction_gray(gray2, color=255)
    if gray1 is None or gray2 is None:
        return 0
    # Resize second image to match first if needed
    if gray1.shape != gray2.shape:
        gray2 = cv2.resize(gray2, (gray1.shape[1], gray1.shape[0]))

    score, _ = ssim(gray1, gray2, full=True)
    return score


icons = [(Path(p).stem, cv2.imread(p)) for p in glob.glob('assets/*.png')]


def _parse_name_category(key: str, text: str, img: cv2.typing.MatLike) -> t.Dict[str, t.Any]:
    # Expect two lines: line1 = Name, line2 = Category
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    name = lines[0] if len(lines) >= 1 else None
    category = lines[1] if len(lines) >= 2 else None
    # Clean common OCR noise
    if name:
        name = re.sub(r'^[0-9\W_]+', '', name).strip()
    if category:
        category = re.sub(r'^[^A-Za-z0-9]+', '', category).strip()
    return {'name': name, 'category': category}


def _parse_number(key: str, text: str, img: cv2.typing.MatLike) -> t.Dict[str, t.Any]:
    m = re.search(r'([0-9]+)', text)
    value = int(m.group(1)) if m else None
    return {key: value}


def _parse_features(key: str, text: str, img: cv2.typing.MatLike) -> t.Dict[str, t.Any]:
    feature_width = 205
    icon_width = 68

    h, w = img.shape[:2]

    n_cols = (w + feature_width - 1) // feature_width

    features = {}
    for i in range(n_cols):
        x_start = i * feature_width
        x_end = x_start + feature_width

        # Crop the column
        col = img[:, x_start:x_end]
        # Remove icon area from the left of the column
        if icon_width >= col.shape[1]:
            # If icon_width is larger than the column, skip this column
            continue
        col_content = col[:, icon_width:]
        text = ocr_image(col_content, psm=8)
        col_icon = col[:, :icon_width]
        sim = [(p, _image_similarity(col_icon, icon))
               for (p, icon) in icons if icon is not None]
        (icon_name, score) = max(sim, key=lambda x: x[1])
        if score >= 0.3:
            features = features | _parse_number(
                f"feature_{icon_name}", text, col_content)
    return features


def _parse_vehicle_durability(key: str, text: str, img: cv2.typing.MatLike) -> t.Dict[str, t.Any]:
    m = re.search(r'vehicle\s+durability\s+by\s+([0-9]+)', text)
    return {
        key: int(m.group(1)) if m else None
    }


SPECS = {
    'name_category': {
        'y': ('Top', 5, 'Top', 192),
        'x': ('Left', 150, 'Right', 5),
        'parse': _parse_name_category
    },
    'powerscore': {
        'y': ('Bottom', 328, 'Bottom', 448),
        'x': ('Left', 26, 'Right', 0),
        'parse': _parse_number
    },
    'features': {
        'y': ('Bottom', 178, 'Bottom', 268),
        'x': ('Left', 26, 'Right', 26),
        'parse': _parse_features
    },
    'durability': {
        'y': ('Bottom', 95, 'Bottom', 178),
        'x': ('Right', 170, 'Right', 320),
        'parse': _parse_number
    },
    'mass': {
        'y': ('Bottom', 28, 'Bottom', 100),
        'x': ('Right', 170, 'Right', 326),
        'parse': _parse_number
    },
    'vehicle_durability': {
        'parse': _parse_vehicle_durability
    }
}


def extract_specifications(bbox: cv2.typing.MatLike):
    info: t.Dict[str, t.Any] = {
        'text': ocr_image(bbox)
    }
    for key in SPECS.keys():
        try:
            spec = SPECS[key]
            needs_crop = spec.get('x') is not None and spec.get('y') is not None
            crop = crop_by_spec(bbox, spec) if needs_crop else bbox
            text_nc = ocr_image(crop) if needs_crop else info['text']
            parse = spec.get('parse')
            info = info | (parse(key, text_nc, crop) if parse is not None else {key: text_nc})
        except Exception as e:
            print(f"[!] Error during OCR specification {key}:", e)
    return info
