# review_gen — 三份 JSON 驱动的审片工程生成器（端到端）

- `generate.py` — 主程序：generate → check → render（超上限自动分段拼接）→ mix 四阶段，每阶段一行 JSON，失败即停
- `hooks.py` — 场景类型钩子注册表（generic / magnifier / screenrec / brand_card）；新增类型 = 加一个钩子类并注册
- `defaults.py` — 设计系统常量（90% 覆盖层 / 字幕样式 / 提亮色 / 缓动 / 轨道分配）

## 输入

1. `master.json`：母版 path / fps / duration / 可选 expected_inode（强制重链 + samefile 断言）
2. `subtitle-timeline.json`：cues + highlight.accent / highlight.risk 高亮词表
3. `overlay-timeline.json`：场景槽位，每个 scene 带 type 字段；screenrec 场景加 video 字段

骨架见 `../../templates/`；推荐用 `../init_video.sh` 自动生成。

## 用法

```bash
python3 generate.py --master master.json --subtitles subtitle-timeline.json \
    --overlay overlay-timeline.json --keyframes <N>-master/hyperframes-keyframes \
    --start 10 --end 20 --name review-sample-10-20 --title "第N条·10至20秒抽检" \
    --out-dir . --check --render --mix --bgm /path/to/bgm.wav --voice-i -13.2
```

- `--check`：hyperframes check 一行摘要（0 error 才继续）
- `--render`：标准质量渲染；预计超单次上限时按「场景间纯母版空档 + 字幕空档 + 帧对齐」分段 + ffmpeg -c copy 无损拼接
- `--mix`：调 `../mix_finalize.py` 混音收口；BGM 无默认，必须 `--bgm` 显式传入；含长静音段窗口 `--voice-i -13.2`，否则默认 -16
