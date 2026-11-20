"""DEM(수치표고모델)으로 도로 구간의 경사를 계산한다.

DEM 파일 위치: 환경변수 DEM_PATH, 없으면 data/raw/dem/ 안의 .tif 또는 .img
경사 부호: 이동 방향 기준으로 + 오르막, - 내리막 (단위 %)
주의: DEM 해상도보다 짧은 급경사나 건물 진입로의 경사는 정확하지 않을 수 있다.
사용 순서: FABDEM(건물·나무 높이를 제거한 30m 자료) > Copernicus(건물 높이가 섞여 있어 보정해서 사용).
"""
import math
import os
from pathlib import Path

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

DEM_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "dem"
MIN_WINDOW_M = 10.0     # 경사를 계산하는 최소 간격
MAX_GRADE = 30.0        # 이보다 큰 값은 DEM 오차로 보고 잘라낸다
METERS_PER_DEGREE = 111_320
COARSE_WINDOW_CELLS = 2     # 30m 자료는 잡음이 커서 경사를 2칸(약 60m) 간격으로 계산


def find_dem():
    """사용할 DEM 파일 경로. 없으면 None."""
    env = os.environ.get("DEM_PATH")
    if env:
        return Path(env) if Path(env).exists() else None
    files = list(DEM_DIR.glob("*.tif")) + list(DEM_DIR.glob("*.img"))
    return min(files, key=lambda f: ("copernicus" in f.name.lower(), f.name), default=None)


def remove_surface_bumps(z, size=3):
    """좁게 튀어나온 건물 높이를 깎는다 (모폴로지 열림). 평평하거나 고르게 기운 지형은 그대로 남는다."""
    def scan(values, pick):
        padded = np.pad(values, size // 2, mode="edge")
        return pick(sliding_window_view(padded, (size, size)), axis=(2, 3))
    return scan(scan(z, np.min), np.max)


class Dem:
    """필요한 범위만 메모리에 읽어 위도·경도의 고도를 돌려준다."""

    def __init__(self, path, bounds):
        """bounds = (서쪽 경도, 남쪽 위도, 동쪽 경도, 북쪽 위도)"""
        import rasterio
        from rasterio.warp import transform_bounds
        from rasterio.windows import Window, from_bounds

        with rasterio.open(path) as ds:
            if ds.crs is None:
                raise ValueError(f"DEM에 좌표계 정보가 없습니다: {path}")
            box = transform_bounds("EPSG:4326", ds.crs, *bounds)
            win = from_bounds(*box, transform=ds.transform)
            col0 = max(int(math.floor(win.col_off)) - 2, 0)
            row0 = max(int(math.floor(win.row_off)) - 2, 0)
            col1 = min(int(math.ceil(win.col_off + win.width)) + 2, ds.width)
            row1 = min(int(math.ceil(win.row_off + win.height)) + 2, ds.height)
            if col1 <= col0 or row1 <= row0:
                raise ValueError(f"DEM이 조사 지역을 포함하지 않습니다: {path}")
            window = Window(col0, row0, col1 - col0, row1 - row0)
            self.z = ds.read(1, window=window, masked=True).astype("float64").filled(np.nan)
            self.inverse = ~ds.window_transform(window)
            self.crs = ds.crs
            self.is_lonlat = ds.crs.to_epsg() == 4326
            res = abs(ds.transform.e)
            self.resolution_m = res * METERS_PER_DEGREE if ds.crs.is_geographic else res
        self.window_m = max(MIN_WINDOW_M, self.resolution_m)
        name = Path(path).name.lower()
        if "copernicus" in name:
            self.z = remove_surface_bumps(self.z)
        if "copernicus" in name or "fabdem" in name:
            self.window_m = self.resolution_m * COARSE_WINDOW_CELLS

    def elevations(self, lons, lats):
        """이중선형 보간한 고도(m). DEM 밖이거나 값이 없으면 nan."""
        from rasterio.warp import transform

        xs, ys = lons, lats
        if not self.is_lonlat:
            xs, ys = transform("EPSG:4326", self.crs, list(lons), list(lats))
        xs, ys = np.asarray(xs, dtype=float), np.asarray(ys, dtype=float)
        a, b, c, d, e, f = tuple(self.inverse)[:6]
        cols = a * xs + b * ys + c - 0.5    # 픽셀 가운데가 고도값의 위치
        rows = d * xs + e * ys + f - 0.5

        height, width = self.z.shape
        result = np.full(cols.shape, np.nan)
        inside = (cols >= 0) & (rows >= 0) & (cols <= width - 1) & (rows <= height - 1)
        c0 = np.clip(np.floor(cols[inside]).astype(int), 0, max(width - 2, 0))
        r0 = np.clip(np.floor(rows[inside]).astype(int), 0, max(height - 2, 0))
        c1, r1 = np.minimum(c0 + 1, width - 1), np.minimum(r0 + 1, height - 1)
        tx, ty = cols[inside] - c0, rows[inside] - r0
        top = self.z[r0, c0] * (1 - tx) + self.z[r0, c1] * tx
        bottom = self.z[r1, c0] * (1 - tx) + self.z[r1, c1] * tx
        result[inside] = top * (1 - ty) + bottom * ty
        return result


def load_dem(bounds):
    """DEM을 읽는다. 파일이 없거나 지역을 포함하지 않으면 None (경사 정보 없음으로 처리)."""
    path = find_dem()
    if path is None:
        print("DEM 파일이 없어 경사를 계산하지 않습니다.")
        return None
    try:
        return Dem(path, bounds)
    except ValueError as e:
        print(e)
        return None


def _points_along(coords, fractions):
    """(경도, 위도) 선을 따라 전체 길이의 비율 위치에 있는 점들."""
    line = np.asarray(coords, dtype=float)
    scale = math.cos(math.radians(line[:, 1].mean()))
    steps = np.hypot(np.diff(line[:, 0]) * scale, np.diff(line[:, 1]))
    distance = np.concatenate(([0.0], np.cumsum(steps)))
    if distance[-1] == 0:
        return np.full(len(fractions), line[0, 0]), np.full(len(fractions), line[0, 1])
    at = np.asarray(fractions) * distance[-1]
    return np.interp(at, distance, line[:, 0]), np.interp(at, distance, line[:, 1])


def _short_edge_grade(dem, coords):
    """DEM 간격보다 짧은 구간은 가운데에서 앞뒤로 DEM 간격만큼 떨어진 고도로 경사를 잰다."""
    line = np.asarray(coords, dtype=float)
    scale = math.cos(math.radians(line[:, 1].mean()))
    east, north = (line[-1, 0] - line[0, 0]) * scale, line[-1, 1] - line[0, 1]
    size = math.hypot(east, north)
    if size == 0:
        return None
    lons, lats = _points_along(coords, [0.5])
    reach = dem.window_m / 2 / METERS_PER_DEGREE
    dlon, dlat = east / size * reach / scale, north / size * reach
    z = dem.elevations(np.array([lons[0] - dlon, lons[0] + dlon]), np.array([lats[0] - dlat, lats[0] + dlat]))
    if np.isnan(z).any():
        return None
    return float(np.clip((z[1] - z[0]) / dem.window_m * 100, -MAX_GRADE, MAX_GRADE))


def segment_lines(coords, count):
    """구간을 count개로 나눈 각 조각의 양 끝 (경도, 위도)."""
    lons, lats = _points_along(coords, np.linspace(0, 1, count + 1))
    points = list(zip(lons.tolist(), lats.tolist()))
    return list(zip(points[:-1], points[1:]))


def edge_segments(dem, coords, length_m, follow_terrain=True):
    """구간을 나눠 [(길이 m, 경사 %), ...]로 돌려준다. 고도를 모르면 None.

    coords: 이동 방향 순서의 (경도, 위도) 목록
    follow_terrain=False: 다리·터널. 지면 고도를 따르지 않으므로 양 끝 고도만 쓴다.
    """
    if dem is None or length_m <= 0 or len(coords) < 2:
        return None
    if follow_terrain and length_m < dem.window_m:
        grade = _short_edge_grade(dem, coords)
        return None if grade is None else [(length_m, round(grade, 2))]
    count = max(1, round(length_m / dem.window_m))
    lons, lats = _points_along(coords, np.linspace(0, 1, count + 1))
    z = dem.elevations(lons, lats)
    if not follow_terrain:
        z = np.linspace(z[0], z[-1], count + 1)
    if np.isnan(z).any():
        return None
    piece = length_m / count
    grades = np.clip(np.diff(z) / piece * 100, -MAX_GRADE, MAX_GRADE)
    return [(piece, round(float(g), 2)) for g in grades]
