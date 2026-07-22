# azu-video-cut

给 AI Agent 用的口播知识短视频剪辑工作流 skill：选题 → 口播稿 → 精剪（字幕/覆盖层/混音）→ 封面 → 发布，全流程可复用、可审计。

A reusable workflow skill for AI agents that produces talking-head knowledge short videos: topic → script → fine editing (captions / overlay motion graphics / audio mix) → cover → publish.

---

## 亮点 · Highlights

- **四道人工确认门** — 选题 / 稿件 / 抽检 / 发布四道硬门，Agent 不得跳过，每一步都有小样先行。
  **Four human confirmation gates** — topic, script, 10s sample, publish. No gate, no next step.
- **端到端一条命令** — 三份 JSON 驱动（master / subtitle / overlay），`generate.py --check --render --mix` 从工程生成到渲染混音一次完成。
  **One end-to-end command** — three JSON files in, finished MP4 out (`--check --render --mix`).
- **响度自动收口** — loudnorm 两遍法 + BGM 垫底 + 限幅梯度，实测验收 -14±0.3 LUFS / ≤-1.5 dBTP。
  **Automatic loudness targeting** — two-pass loudnorm + ducked BGM + limiter ladder, verified to -14±0.3 LUFS / ≤-1.5 dBTP.
- **中文字幕样式系统** — 去标点规则、canon 逐字校验、数据驱动高亮词表、安全区与双行长句自适应。
  **Chinese caption system** — no-punctuation rules, canon verbatim check, data-driven highlights, safe-zone aware.
- **封面规范** — 唯一承诺先行、文字逐字确认后才出图、PIL 合成品牌角标。
  **Cover style guide** — promise-first copy, confirmed text before any image, badge composited via PIL.
- **省 token 设计** — 所有脚本每阶段只输出一行 JSON 进度/结论，失败即停并报告阶段。
  **Token-frugal** — every script stage prints exactly one JSON line; fail-fast with stage report.

## 安装 · Installation

把 `azu-video-cut/` 整个目录放进你的 Agent skills 目录：

Drop the `azu-video-cut/` directory into your agent's skills directory:

- Claude Code: `~/.claude/skills/`
- Codex: `~/.codex/skills/`
- Kimi 等其他 Agent：对应的等效 skills 目录

## 快速开始 · Quick Start

1. **首次触发**：Agent 会自动走 `references/setup.md` 的五步配置引导——环境依赖 / 转录 API Key / 品牌资产 / BGM 入库 / 冒烟测试，全部就位才开工。
   **First run**: the agent walks you through a five-step setup (`references/setup.md`) — dependencies, transcription API key, brand assets, BGM, and a smoke test.
2. **之后每次开剪**，一句话即可：
   **After that, one sentence per video**:

   > 开剪第N条，母版在 /path/to/初剪视频.mov

   脚手架会自动建工程目录、实测母版规格、生成三份 JSON 骨架，然后按确认门逐步推进。

## 目录结构 · Structure

```
azu-video-cut/
├── SKILL.md          ← skill 本体（确认门 + 一页速查 + 路由表）
├── scripts/          ← init_video.sh / mix_finalize.py / review_gen/（端到端生成器）
├── references/       ← workflow / setup / cover-style-guide / checklist（按需读取）
└── templates/        ← 选题卡 / 发布记录 / 三份 JSON 骨架
```

## 系统要求 · Requirements

- ffmpeg / ffprobe（剪辑、混音、验证全链路）
- Node.js 22+（HyperFrames 覆盖层渲染，经 npx 调用，无需全局安装）
- Python 3 + Pillow（封面角标合成）
- 一个词级转录服务的 API Key（或本地 whisper fallback）——只写入本机 `.env`，绝不进入对话或分享文件

## License

MIT（待确认 / TBD）— © azu-video-cut contributors
