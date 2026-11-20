"""360도 사진을 앞·오른쪽·뒤·왼쪽 일반 화면으로 나눈다.

360도 사진은 화면이 둥글게 휘어 있어, 일반 사진으로 학습한 모델이 장애물을 잘 찾지 못한다.
view 값: "photo" 일반 사진 그대로, "0" 앞, "90" 오른쪽, "180" 뒤, "270" 왼쪽
"""
import math
from functools import lru_cache

import cv2
import numpy as np

from config import MAPILLARY_DIR

YAWS = (0, 90, 180, 270)
PITCH = -10         # 계단·턱이 잘 보이도록 살짝 아래를 본다
FOV = 100           # 화면 경계의 장애물이 잘리지 않게 옆 화면과 조금 겹친다
SIZE = 640
IMAGES = MAPILLARY_DIR / "images"
IMAGES_HD = MAPILLARY_DIR / "images_hd"
VIEWS = MAPILLARY_DIR / "views"


def is_panorama(image):
    height, width = image.shape[:2]
    return abs(width / height - 2) < 0.03


@lru_cache(maxsize=16)
def _maps(width, height, yaw):
    """화면의 각 픽셀이 360도 사진의 어디에 해당하는지 계산한다."""
    focal = SIZE / 2 / math.tan(math.radians(FOV) / 2)
    axis = np.arange(SIZE, dtype=np.float32) - (SIZE - 1) / 2
    x, y = np.meshgrid(axis, axis)
    z = np.full_like(x, focal)
    pitch, turn = math.radians(PITCH), math.radians(yaw)
    y2 = y * math.cos(pitch) - z * math.sin(pitch)
    z2 = y * math.sin(pitch) + z * math.cos(pitch)
    x3 = x * math.cos(turn) + z2 * math.sin(turn)
    z3 = -x * math.sin(turn) + z2 * math.cos(turn)
    lon = np.arctan2(x3, z3)
    lat = np.arcsin(-y2 / np.sqrt(x3 ** 2 + y2 ** 2 + z3 ** 2))
    map_x = (lon / (2 * math.pi) + 0.5) * width
    map_y = (0.5 - lat / math.pi) * height
    return map_x.astype(np.float32), map_y.astype(np.float32)


def render_view(panorama, yaw):
    height, width = panorama.shape[:2]
    return cv2.remap(panorama, *_maps(width, height, yaw), cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)


def image_path(image_id):
    """고화질 사진이 있으면 그것을 쓴다."""
    hd = IMAGES_HD / f"{image_id}.jpg"
    return hd if hd.exists() else IMAGES / f"{image_id}.jpg"


def frames(image_id):
    """사진 하나에서 탐지할 화면들을 (view, 이미지)로 돌려준다. 깨진 사진이면 빈 목록."""
    image = cv2.imread(str(image_path(image_id)))
    if image is None:
        return []
    if is_panorama(image):
        return [(str(yaw), render_view(image, yaw)) for yaw in YAWS]
    return [("photo", image)]


def frame(image_id, view):
    """저장된 사진에서 화면 하나를 만든다."""
    image = cv2.imread(str(image_path(image_id)))
    return image if view == "photo" else render_view(image, int(view))


def view_file(image_id, view):
    return VIEWS / f"{image_id}_{view}.jpg"
