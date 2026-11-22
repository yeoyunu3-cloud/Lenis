"""서비스 지역: 부산광역시 전체.

BUSAN_BOUNDS는 부산광역시 행정 경계를 조금 넉넉하게 감싼 사각형이다 (서, 남, 동, 북).
도로망은 실제 행정 경계(OSM)로 받고, 이 사각형은 DEM 자르기·좌표 검사처럼 빠른 판단에 쓴다.
"""
BUSAN_PLACE = "부산광역시, 대한민국"
BUSAN_BOUNDS = (128.75, 34.87, 129.32, 35.40)
MAP_CENTER = (35.117, 129.0375)   # 화면 첫 위치 (초량동)


def in_busan(lat, lon):
    west, south, east, north = BUSAN_BOUNDS
    return south <= lat <= north and west <= lon <= east
