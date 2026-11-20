#!/bin/bash
# 편한길로 임시 배포: 이 노트북에서 서버를 켜고 cloudflared로 외부 https 주소를 만든다.
# 노트북이 켜져 있고 이 창이 열려 있는 동안만 접속된다. 다시 실행하면 주소가 바뀐다.
# 끄기: Ctrl + C
cd "$(dirname "$0")"
PORT=8000

if [ ! -x server/.venv/bin/python ]; then
  echo "server/.venv가 없습니다. 먼저 실행하세요:"
  echo "  cd server && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

caffeinate -i -w $$ &           # 배포 중에는 노트북이 잠들지 않게 한다
(cd server && exec .venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port $PORT --log-level warning) &
SERVER=$!
cloudflared tunnel --no-autoupdate --url "http://localhost:$PORT" > 배포_로그.txt 2>&1 &
TUNNEL=$!
trap 'kill $SERVER $TUNNEL 2>/dev/null; rm -f 배포_주소.txt; echo "배포를 껐습니다."' EXIT

for _ in $(seq 30); do curl -s -o /dev/null "localhost:$PORT/api/profiles" && break; sleep 1; done
# 첫 사용자가 기다리지 않도록 경로 계산을 한 번 미리 해 둔다
curl -s -o /dev/null -X POST "localhost:$PORT/api/route" -H 'Content-Type: application/json' \
  -d '{"start":[35.120039,129.0345155],"end":[35.118028,129.039297],"profile":"stroller"}'

for _ in $(seq 60); do
  URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' 배포_로그.txt | head -1)
  [ -n "$URL" ] && break
  sleep 1
done
if [ -z "$URL" ]; then
  echo "외부 주소를 만들지 못했습니다. 배포_로그.txt를 확인하세요."
  exit 1
fi
echo "$URL" > 배포_주소.txt
echo "배포 주소: $URL"
echo "휴대폰에서 이 주소를 열고, 공유 메뉴의 '홈 화면에 추가'로 앱처럼 쓸 수 있습니다."
wait $SERVER
