#!/usr/bin/env bash
# Fetch SIGARRA timetable events for every UC occurrence listed in data/subjects.json.
#
#   scripts/fetch_timetables.sh              # fetch all, skipping already-downloaded ones
#   scripts/fetch_timetables.sh 589589       # fetch only these occurrence ids
#   FORCE=1 scripts/fetch_timetables.sh      # re-download even if cached
#   DELAY=3 scripts/fetch_timetables.sh      # seconds between requests (default 1.5)
#
# No login required: the endpoint is public. It IS behind Cloudflare, which
# rejects requests that don't look like a browser (403) and throttles bursts,
# so we send a full Chrome header set and back off when refused.
set -uo pipefail
cd "$(dirname "$0")/.."   # scripts live in scripts/, data lives at the root

YEAR=${YEAR:-2026}
PERIODS=${PERIODS:-"1 2 4 5 8"}
DELAY=${DELAY:-1.5}
FORCE=${FORCE:-0}
OUT=data/raw
FAILED=data/failed.txt
BASE="https://sigarra.up.pt/calendarios-api/api/v1/events/fcup/uc"
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36'

# The full set is required together; dropping any one of these gets a 403.
HDRS=(
  -A "$UA"
  -H 'Accept: application/json, text/plain, */*'
  -H 'Accept-Language: pt-PT,pt;q=0.9,en;q=0.8'
  -H 'sec-ch-ua: "Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"'
  -H 'sec-ch-ua-mobile: ?0'
  -H 'sec-ch-ua-platform: "Linux"'
  -H 'Sec-Fetch-Dest: empty'
  -H 'Sec-Fetch-Mode: cors'
  -H 'Sec-Fetch-Site: same-origin'
)

QS="academic_year=${YEAR}"
for p in $PERIODS; do QS="${QS}&period=${p}"; done
QS="${QS}&lang=pt"

mkdir -p "$OUT"
if [ $# -gt 0 ]; then IDS="$*"; else IDS=$(jq -r '[.[].occurrence_id] | unique | .[]' data/subjects.json); fi

total=$(echo "$IDS" | wc -w)
echo "Fetching $total occurrence(s) -> $OUT/  (year=$YEAR periods='$PERIODS' delay=${DELAY}s)"
: > "$FAILED"
ok=0; skip=0; fail=0; i=0

for id in $IDS; do
  i=$((i + 1))
  dest="$OUT/${id}.json"

  # Treat a cached file as done only if it is valid, non-empty JSON.
  if [ "$FORCE" != "1" ] && [ -s "$dest" ] && jq -e 'has("data")' "$dest" >/dev/null 2>&1; then
    skip=$((skip + 1)); continue
  fi

  code=""
  for attempt in 1 2 3 4; do
    code=$(curl -sS -m 40 --compressed "${HDRS[@]}" \
             -H "Referer: https://sigarra.up.pt/fcup/pt/ucurr_geral.ficha_uc_view?pv_ocorrencia_id=${id}" \
             -o "$dest.part" -w '%{http_code}' \
             "${BASE}/${id}/?${QS}") || code="000"
    [ "$code" = "200" ] && break
    # 403 here means "slow down", not "forbidden forever": back off and retry.
    case "$code" in
      403|429|500|502|503|504|000) sleep $((attempt * attempt * 5)) ;;
      *) break ;;
    esac
  done

  if [ "$code" = "200" ] && jq -e 'has("data")' "$dest.part" >/dev/null 2>&1; then
    mv "$dest.part" "$dest"
    ok=$((ok + 1))
  else
    rm -f "$dest.part"
    fail=$((fail + 1))
    echo "$id http=$code" >> "$FAILED"
  fi

  printf '\r  [%d/%d] ok=%d cached=%d failed=%d    ' "$i" "$total" "$ok" "$skip" "$fail"
  sleep "$DELAY"
done

echo
echo "done: $ok fetched, $skip cached, $fail failed"
if [ "$fail" -gt 0 ]; then
  echo "failures in $FAILED - re-run the script to retry just those"
fi
exit 0
