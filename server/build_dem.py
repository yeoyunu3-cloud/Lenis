"""부산 전체를 덮는 DEM 한 장을 만든다: FABDEM 도엽 4장을 이어 붙이고 부산 범위로 자른다.

준비: data/raw/dem/ 에 fabdem_n34_e128.tif, fabdem_n34_e129.tif, fabdem_n35_e128.tif, fabdem_n35_e129.tif
실행: cd server && .venv/bin/python build_dem.py  →  data/raw/dem/fabdem_busan.tif
slope.find_dem()은 이름순으로 fabdem_busan.tif를 먼저 고른다.
"""
from pathlib import Path

import rasterio
from rasterio.merge import merge

from area import BUSAN_BOUNDS

DEM_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "dem"
TILES = ["fabdem_n34_e128.tif", "fabdem_n34_e129.tif", "fabdem_n35_e128.tif", "fabdem_n35_e129.tif"]
OUT = DEM_DIR / "fabdem_busan.tif"


def main():
    sources = [rasterio.open(DEM_DIR / name) for name in TILES]
    try:
        mosaic, transform = merge(sources, bounds=BUSAN_BOUNDS)
        profile = sources[0].profile | {
            "driver": "GTiff", "height": mosaic.shape[1], "width": mosaic.shape[2],
            "transform": transform, "compress": "deflate", "tiled": True,
        }
    finally:
        for s in sources:
            s.close()
    with rasterio.open(OUT, "w", **profile) as dst:
        dst.write(mosaic)
    print(f"{OUT.name}: {mosaic.shape[2]}x{mosaic.shape[1]} 픽셀")


if __name__ == "__main__":
    main()
