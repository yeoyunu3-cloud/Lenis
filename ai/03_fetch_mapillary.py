"""3단계: Mapillary에서 부산 도심의 거리 사진과 위치를 받는다.

토큰: 환경변수 MAPILLARY_TOKEN. 없거나 사진을 볼 수 없는 값이면 화면에 안 보이게 입력받는다.
      개발자 페이지의 Client token 칸에서 View를 눌러 나온 Access Token을 쓴다 (Client secret 아님).
출력: data/processed/mapillary/images.csv, images/<id>.jpg, images_hd/<id>.jpg (360도 사진의 고화질본)
사진 출처 표기: "거리 사진 출처: Mapillary 기여자 (CC BY-SA 4.0)"
"""
import csv
import getpass
import os
import time
from concurrent.futures import ThreadPoolExecutor

import requests

from config import MAPILLARY_DIR

API = "https://graph.mapillary.com/images"
FIELDS = "id,thumb_1024_url,thumb_2048_url,is_pano,computed_geometry,geometry,compass_angle,captured_at"
COLUMNS = ["image_id", "lat", "lon", "angle", "captured_at", "is_pano", "url", "url_hd"]
# (서쪽 경도, 남쪽 위도, 동쪽 경도, 북쪽 위도) — AI 성능 검증에 쓸 부산 도심
BUSAN_AREA = (129.00, 35.06, 129.12, 35.20)
TEST_BBOX = "2.29,48.85,2.30,48.86"     # 토큰 확인용: 사진이 많은 에펠탑 주변


def tiles(w, s, e, n, step=0.005):
    """넓은 범위를 작은 칸으로 나눈다 (API가 넓은 범위를 한 번에 못 받음)."""
    x = w
    while x < e - 1e-9:
        y = s
        while y < n - 1e-9:
            yield (x, y, min(x + step, e), min(y + step, n))
            y += step
        x += step


def can_read_images(token):
    """Client secret은 오류 없이 0장만 돌려주므로 사진이 많은 곳에서 먼저 시험한다."""
    try:
        r = requests.get(API, headers={"Authorization": f"OAuth {token}"},
                         params={"fields": "id", "bbox": TEST_BBOX, "limit": 5}, timeout=60)
    except requests.RequestException as e:
        raise SystemExit(f"Mapillary에 연결하지 못했습니다: {type(e).__name__}")
    return r.status_code == 200 and len(r.json().get("data", [])) > 0


def get_token():
    token = os.environ.get("MAPILLARY_TOKEN", "").strip()
    if token.isascii() and token and can_read_images(token):
        return token
    for _ in range(3):
        token = getpass.getpass("Access Token 붙여 넣고 Enter (글자는 안 보입니다): ").strip().strip("'\"")
        if token.isascii() and token and can_read_images(token):
            return token
        print("이 값으로는 사진을 볼 수 없습니다. Client token 칸의 Access Token을 복사하세요.")
    raise SystemExit("토큰 확인에 3번 실패했습니다. 기존 파일은 바꾸지 않았습니다.")


def fetch_tile(token, tile):
    """칸 하나의 사진 정보. 끝내 실패하면 None."""
    for wait in (0, 3, 10):
        time.sleep(wait)
        try:
            r = requests.get(API, headers={"Authorization": f"OAuth {token}"}, timeout=60, params={
                "fields": FIELDS, "bbox": ",".join(f"{v:.6f}" for v in tile), "limit": 2000,
            })
        except requests.RequestException:
            continue
        if r.status_code == 200:
            return r.json().get("data", [])
    return None


def fetch_meta(token):
    cells = list(tiles(*BUSAN_AREA))
    print(f"부산 도심 {len(cells)}칸에서 사진을 찾는 중...")
    with ThreadPoolExecutor(4) as pool:
        results = list(pool.map(lambda cell: fetch_tile(token, cell), cells))
    rows = {}
    for images in results:
        for im in images or []:
            if str(im["id"]) in rows or not im.get("thumb_1024_url"):
                continue
            lon, lat = (im.get("computed_geometry") or im["geometry"])["coordinates"]
            rows[str(im["id"])] = {
                "image_id": str(im["id"]), "lat": lat, "lon": lon,
                "angle": im.get("compass_angle"), "captured_at": im.get("captured_at"),
                "is_pano": bool(im.get("is_pano")),
                "url": im["thumb_1024_url"], "url_hd": im.get("thumb_2048_url") or "",
            }
    return list(rows.values()), sum(r is None for r in results)


def save_photo(url, path, image_id):
    """사진 하나를 받는다. 성공하거나 이미 있으면 True."""
    if path.exists():
        return True
    try:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
    except requests.RequestException as e:
        print("실패:", image_id, type(e).__name__)
        return False
    if not r.content.startswith(b"\xff\xd8"):      # JPEG가 아니면 저장하지 않는다
        print("실패:", image_id, "사진 파일이 아님")
        return False
    path.write_bytes(r.content)
    return True


def download(row):
    saved = save_photo(row["url"], MAPILLARY_DIR / "images" / f"{row['image_id']}.jpg", row["image_id"])
    if row["is_pano"] and row["url_hd"]:    # 360도 사진은 나눠서 쓰므로 고화질이 필요하다
        save_photo(row["url_hd"], MAPILLARY_DIR / "images_hd" / f"{row['image_id']}.jpg", row["image_id"])
    return saved


if __name__ == "__main__":
    token = get_token()
    print("토큰 확인 완료")
    rows, failed_cells = fetch_meta(token)
    if not rows:
        raise SystemExit("찾은 사진이 없어 기존 파일을 바꾸지 않았습니다.")
    (MAPILLARY_DIR / "images").mkdir(parents=True, exist_ok=True)
    (MAPILLARY_DIR / "images_hd").mkdir(parents=True, exist_ok=True)
    with open(MAPILLARY_DIR / "images.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"찾은 사진: {len(rows)}장 (확인 실패 {failed_cells}칸)")
    with ThreadPoolExecutor(8) as pool:
        saved = sum(pool.map(download, rows))
    hd = len(list((MAPILLARY_DIR / "images_hd").glob("*.jpg")))
    print(f"다운로드 완료: {saved}장 (360도 고화질 {hd}장)")
