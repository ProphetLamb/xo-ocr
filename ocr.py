import mss
from PIL import Image
import cv2
import numpy as np
import scipy
import scipy.ndimage
import typing as t

import pytesseract


def take_screenshot() -> Image.Image:
    with mss.mss() as sct:
        monitor = sct.monitors[0]  # full virtual screen
        sct_img = sct.grab(monitor)
        img = Image.frombytes("RGB", sct_img.size, sct_img.rgb)
        return img


def _cross_kernel(size: int, cross: int) -> np.ndarray:
    """Returns a kernel of given size with a origin symmetric cross shape.

    Args:
        size (int): The width and height of the kernel.
        cross (int): The width of the cross.

    Returns:
        np.ndarray: The kernel as a numpy array of the shape (size, size).
    """
    kernel = np.zeros((size, size), np.uint8)
    # cross shaped kernel
    size_2 = size // 2
    cross_2 = cross // 2
    kernel[size_2 - cross_2:size_2 + cross_2 + 1, size_2] = 1
    return kernel


def _boundary_box_area(bbox: t.Tuple[slice, slice]) -> int:
    """Calculate the area of a boundary box.

    Args:
        bbox (t.Tuple[slice, slice]): The scipy boundary box

    Returns:
        int: The area of the boundary box
    """
    return abs(bbox[0].stop - bbox[0].start) * abs(bbox[1].stop - bbox[1].start)


def _measure_bright_box(mask: np.ndarray) -> t.List[tuple]:
    """Measure the area of the largest shape in the given mask.

    Args:
        mask (np.ndarray): The processed monochrome image

    Returns:
        int: The area of the boundary box of largest shape in the given mask
        t.List[tuple]: The boundary boxes of all the shapes in the given mask
    """
    labels, n = scipy.ndimage.label(mask, np.ones((3, 3)))
    # get the bounding boxes of the bright boxes
    bboxes: t.List[tuple] = scipy.ndimage.find_objects(labels)
    bboxes.sort(key=lambda bbox: _boundary_box_area(bbox), reverse=True)
    # return the area of the largest bounding box
    return bboxes


def box_extraction(pil_img: Image.Image, color=153):
    img = np.array(pil_img.convert('L'))
    return box_extraction_gray(img, color=color)


def box_extraction_gray(img: np.ndarray, color=153):
    kernel = _cross_kernel(3, 3)
    # apply thresholding
    # the dark box will turn bright if its a match, so we ought to remove the dark, but keep the bright at the threshold
    img = (img == color) * 255
    # finally apply dilation and erosion to complete possible holes in the bright box border
    img = scipy.ndimage.binary_dilation(
        img, structure=kernel, iterations=2).astype(img.dtype)
    img = scipy.ndimage.binary_erosion(
        img, structure=kernel, iterations=2).astype(img.dtype)
    bboxes = _measure_bright_box(img)
    if len(bboxes) == 0:
        return None
    y, x = bboxes[0]

    return (x.start, y.start, x.stop - x.start, y.stop - y.start)

def crop_box_extraction_gray(img: np.ndarray, color=153):
    bbox = box_extraction_gray(img, color=color)
    if bbox is None:
        return None
    x, y, w, h = bbox
    return img[y:y+h, x:x+w]


def _clamp(v: int, a: int, b: int):
    return max(a, min(b, v))


def pil2openCv(pil_img: Image.Image) -> cv2.typing.MatLike:
    open_cv_image = np.array(pil_img)
    # Convert RGB to BGR
    return open_cv_image[:, :, ::-1].copy()


def crop_by_spec(img: cv2.typing.MatLike, spec: t.Dict[str, t.Tuple[str, int, str, int]]):
    """
    spec is a dict with keys: ('y_type','y1','y2_type','y2') where y_type is 'Top' or 'Bottom'
    and x types are 'Left' or 'Right'. Example:
      {'y': ('Top', 5, 'Top', 192), 'x': ('Left', 150, 'Right', 5)}
    Returns cropped image (numpy array).
    """
    h, w = img.shape[:2]

    # Y coordinates
    y1_type, y1_val, y2_type, y2_val = spec['y']
    if y1_type.lower() == 'top':
        y1 = int(y1_val)
    else:  # Bottom
        y1 = int(h - y1_val)
    if y2_type.lower() == 'top':
        y2 = int(y2_val)
    else:
        y2 = int(h - y2_val)

    # X coordinates
    x1_type, x1_val, x2_type, x2_val = spec['x']
    if x1_type.lower() == 'left':
        x1 = int(x1_val)
    else:  # Right
        x1 = int(w - x1_val)
    if x2_type.lower() == 'left':
        x2 = int(x2_val)
    else:
        x2 = int(w - x2_val)

    # Ensure ordering
    x_min, x_max = sorted((x1, x2))
    y_min, y_max = sorted((y1, y2))

    # Clamp to image bounds
    x_min = _clamp(x_min, 0, w - 1)
    x_max = _clamp(x_max, 0, w - 1)
    y_min = _clamp(y_min, 0, h - 1)
    y_max = _clamp(y_max, 0, h - 1)

    if x_max <= x_min or y_max <= y_min:
        raise ValueError(
            f"Invalid crop box computed: x({x_min},{x_max}) y({y_min},{y_max})")

    return img[y_min:y_max, x_min:x_max]


def ocr_image(img: cv2.typing.MatLike, oem=3, psm=6):
    # Convert to grayscale and simple threshold to improve OCR
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Resize small crops to improve accuracy
    h, w = gray.shape
    scale = 2 if max(h, w) < 600 else 1
    if scale != 1:
        gray = cv2.resize(gray, (w*scale, h*scale),
                          interpolation=cv2.INTER_LINEAR)
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    config = f'--oem {oem} --psm {psm}'
    text = pytesseract.image_to_string(th, config=config)
    return text.strip()
