#!/bin/bash
# init_video.sh — 新视频开工脚手架（口播知识短视频剪辑管线）
# 用法: scripts/init_video.sh 第五条 /path/to/用户初剪母版.mov [--out-dir /tmp/test]
# 输出: 一行 JSON 摘要（目录/时长/fps/inode），失败打印 {"ok":false,...} 并非零退出
set -euo pipefail

if [ $# -lt 2 ]; then
  echo '{"ok":false,"error":"用法: init_video.sh <第N条> <母版路径> [--out-dir DIR]"}' >&2; exit 2
fi
LABEL="$1"; MASTER="$2"; OUTBASE="edit"
if [ "${3:-}" = "--out-dir" ]; then
  [ $# -ge 4 ] || { echo '{"ok":false,"error":"--out-dir 缺少目录"}'; exit 2; }
  OUTBASE="$4"
fi

case "$LABEL" in
  第一条) ORD=first;;  第二条) ORD=second;; 第三条) ORD=third;;
  第四条) ORD=fourth;; 第五条) ORD=fifth;;  第六条) ORD=sixth;;
  第七条) ORD=seventh;; 第八条) ORD=eighth;; 第九条) ORD=ninth;;
  第十条) ORD=tenth;;
  *)
    ORD=$(printf '%s' "$LABEL" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9._-]/-/g; s/^-*//; s/-*$//; s/--*/-/g')
    [ -n "$ORD" ] || { echo "{\"ok\":false,\"error\":\"未识别序号或安全 slug: $LABEL\"}"; exit 1; }
    ;;
esac

[ -f "$MASTER" ] || { echo "{\"ok\":false,\"error\":\"母版不存在: $MASTER\"}"; exit 1; }

DIR="$OUTBASE/${ORD}-master"
mkdir -p "$DIR/transcripts" "$DIR/assets" "$DIR/hyperframes-keyframes" "$DIR/outputs"

# 母版进 assets/（硬链接优先，跨设备复制），记录 inode
DEST="$DIR/assets/$(basename "$MASTER")"
if [ ! -e "$DEST" ]; then
  ln "$MASTER" "$DEST" 2>/dev/null || cp -p "$MASTER" "$DEST"
fi
if INODE=$(stat -f '%i' "$DEST" 2>/dev/null); then
  :
elif INODE=$(stat -c '%i' "$DEST" 2>/dev/null); then
  :
else
  echo '{"ok":false,"error":"无法读取母版 inode"}'; exit 1
fi
ABS_DEST=$(cd "$(dirname "$DEST")" && pwd)/$(basename "$DEST")

# ffprobe 实测规格
PROBE=$(ffprobe -v error -select_streams v:0 \
  -show_entries stream=width,height,avg_frame_rate -show_entries format=duration \
  -of json "$DEST")
read W H FPS DUR < <(python3 -c "
import json,sys, fractions
info=json.loads('''$PROBE''')
st=info['streams'][0]
fps=round(float(fractions.Fraction(st['avg_frame_rate'])))
print(st['width'], st['height'], fps, round(float(info['format']['duration']),3))
")

# master.json（对齐 review_gen/generate.py 输入契约）
cat > "$DIR/master.json" <<EOF
{
  "path": "$ABS_DEST",
  "fps": $FPS,
  "duration": $DUR,
  "expected_inode": $INODE,
  "note": "$LABEL 锁定母版（用户初剪，唯一权威）；由 init_video.sh 生成"
}
EOF

# 字幕骨架（结构对齐 fourth-master/subtitle-timeline.json，cues 待填）
cat > "$DIR/subtitle-timeline.json" <<EOF
{
  "version": 1,
  "source": "$ABS_DEST",
  "output": { "width": $W, "height": $H, "fps": $FPS },
  "language": "zh-CN",
  "style": {
    "font_family": "Noto Sans JP",
    "font_size_px": 62,
    "two_line_font_size_px": 57,
    "font_weight": 700,
    "primary_color": "#FFF8EA",
    "accent_color": "#F2B84B",
    "risk_color": "#EF514A",
    "background": "rgba(8, 10, 14, 0.82)",
    "bottom_margin_px": 82,
    "max_width_percent": 72,
    "max_lines": 2,
    "note": "字幕在所有覆盖层之后最后合成。底部约 154px 为字幕安全区。字幕不使用标点符号。"
  },
  "corrections": [],
  "highlight": { "accent": [], "risk": [] },
  "cues": []
}
EOF

# 覆盖层骨架（结构对齐 fourth-master/overlay-timeline.json，scenes 待填；
# 每个 scene 需 id/start/end/type（review_gen 钩子类型）/content/asset/payoff）
cat > "$DIR/overlay-timeline.json" <<EOF
{
  "version": 1,
  "source": "$ABS_DEST",
  "output": { "width": $W, "height": $H, "fps": $FPS },
  "speed": 1.0,
  "overlay_opacity": 0.9,
  "scenes": [],
  "notes": "待填。scene.type 取值见 scripts/review_gen/hooks.py（generic/magnifier/screenrec/brand_card）"
}
EOF

echo "{\"ok\":true,\"dir\":\"$DIR\",\"duration_s\":$DUR,\"fps\":$FPS,\"resolution\":\"${W}x${H}\",\"inode\":$INODE}"
