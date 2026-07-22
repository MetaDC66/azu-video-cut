#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
TMP_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/azu-video-cut-smoke.XXXXXX")
trap 'rm -rf "$TMP_ROOT"' EXIT

ffmpeg -y -hide_banner -loglevel error \
  -f lavfi -i color=c=0x182033:s=640x360:r=30:d=6 \
  -f lavfi -i sine=frequency=440:sample_rate=48000:duration=6 \
  -shortest -c:v libx264 -pix_fmt yuv420p -c:a aac "$TMP_ROOT/master.mp4"

ffmpeg -y -hide_banner -loglevel error \
  -f lavfi -i sine=frequency=220:sample_rate=48000:duration=2 \
  -c:a pcm_s16le "$TMP_ROOT/bgm.wav"

bash "$ROOT/scripts/init_video.sh" test-video "$TMP_ROOT/master.mp4" \
  --out-dir "$TMP_ROOT/edit" > "$TMP_ROOT/init-result.json"

mkdir -p "$TMP_ROOT/keyframes/assets"
cat > "$TMP_ROOT/keyframes/index.html" <<'HTML'
<!doctype html><html><head><style>body{margin:0;background:#10131a}</style></head><body></body></html>
HTML
printf '{"version":1}\n' > "$TMP_ROOT/keyframes/hyperframes.json"

python3 "$ROOT/scripts/review_gen/generate.py" \
  --master "$TMP_ROOT/edit/test-video-master/master.json" \
  --subtitles "$TMP_ROOT/edit/test-video-master/subtitle-timeline.json" \
  --overlay "$TMP_ROOT/edit/test-video-master/overlay-timeline.json" \
  --keyframes "$TMP_ROOT/keyframes" \
  --start 0 --end 2 --name generated-review --title "Synthetic smoke test" \
  --out-dir "$TMP_ROOT" > "$TMP_ROOT/generate-result.json"

python3 "$ROOT/scripts/mix_finalize.py" \
  --video "$TMP_ROOT/master.mp4" \
  --bgm "$TMP_ROOT/bgm.wav" \
  --out "$TMP_ROOT/mixed.mp4" \
  --report "$TMP_ROOT/mix-report.json" > "$TMP_ROOT/mix-result.json"

ffprobe -v error -select_streams a:0 \
  -show_entries stream=codec_name,sample_rate,channels \
  -of json "$TMP_ROOT/mixed.mp4" > "$TMP_ROOT/audio-probe.json"

python3 - "$TMP_ROOT" <<'PY'
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
init_result = json.loads((root / "init-result.json").read_text())
mix_report = json.loads((root / "mix-report.json").read_text())
probe = json.loads((root / "audio-probe.json").read_text())["streams"][0]

assert init_result["ok"] is True
assert (root / "edit" / "test-video-master" / "master.json").is_file()
assert (root / "generated-review" / "index.html").is_file()
assert (root / "generated-review" / "assets" / "master.mov").is_file()
assert mix_report["ok"] is True
assert abs(float(mix_report["final"]["I"]) + 14.0) <= 0.3
assert float(mix_report["final"]["TP"]) <= -1.5
assert probe["codec_name"] == "aac"
assert probe["sample_rate"] == "48000"
assert probe["channels"] == 2
print("smoke test passed")
PY
