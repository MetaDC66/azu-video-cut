# azu-video-cut

给 AI Agent 用的口播知识短视频剪辑工作流 skill：选题 → 口播稿 → 精剪（字幕/覆盖层/混音）→ 封面 → 发布，全流程可复用、可审计。

A reusable workflow skill for AI agents that produces talking-head knowledge short videos: topic → script → fine editing (captions / overlay motion graphics / audio mix) → cover → publish.

---

## 亮点 · Highlights

- **四道人工确认门** — 选题 / 稿件 / 抽检 / 发布四道硬门，Agent 不得跳过，每一步都有小样先行。
  **Four human confirmation gates** — topic, script, 10s sample, publish. No gate, no next step.
- **审片合成到交付一条命令** — 已确认的关键帧工程 + 三份 JSON（master / subtitle / overlay）驱动，`generate.py --check --render --mix` 完成检查、渲染与混音；特效场景创作仍需人工确认。
  **One command from approved composition to delivery** — an approved keyframe project plus three JSON timelines drive check, render, and mix; creative scene design remains human-reviewed.
- **响度自动收口** — loudnorm 两遍法 + BGM 垫底 + 限幅梯度，实测验收 -14±0.3 LUFS / ≤-1.5 dBTP。
  **Automatic loudness targeting** — two-pass loudnorm + ducked BGM + limiter ladder, verified to -14±0.3 LUFS / ≤-1.5 dBTP.
- **中文字幕样式系统** — 去标点规则、canon 逐字校验、数据驱动高亮词表、安全区与双行长句自适应。
  **Chinese caption system** — no-punctuation rules, canon verbatim check, data-driven highlights, safe-zone aware.
- **封面规范** — 唯一承诺先行、文字逐字确认后才出图、PIL 合成品牌角标。
  **Cover style guide** — promise-first copy, confirmed text before any image, badge composited via PIL.
- **省 token 设计** — 所有脚本每阶段只输出一行 JSON 进度/结论，失败即停并报告阶段。
  **Token-frugal** — every script stage prints exactly one JSON line; fail-fast with stage report.
- **密钥零接触** — Agent 不索取、不读取、不回显 API Key；用户只在本机私有配置中填写。
  **Zero-touch secrets** — the agent never requests, reads, or echoes API keys; users configure them locally.
- **发布画面风险检查** — 关键帧和最终成片检查工具名称墙、Logo 阵列、下载/安装暗示和批量推广感。
  **Visual publishing checks** — inspect tool/logo walls and download, install, or bulk-promotion cues before delivery.

## 安装 · Installation

把 `azu-video-cut/` 整个目录放进你的 Agent skills 目录：

Drop the `azu-video-cut/` directory into your agent's skills directory:

- Claude Code: `~/.claude/skills/`
- Codex: `~/.codex/skills/`
- Kimi 等其他 Agent：对应的等效 skills 目录

## 快速开始 · Quick Start

1. **首次触发**：Agent 会自动走 `references/setup.md` 的六步配置引导——环境依赖 / 本机转录配置 / 品牌资产 / 项目配置 / BGM / 冒烟测试，全部就位才开工。Agent不会要求你把密钥发进对话。
   **First run**: the agent walks through six setup stages without asking you to paste secrets into chat.
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

## 已验证边界 · Validated Scope

- 当前稳定组合：macOS、Node.js 22+、FFmpeg、Python 3、HyperFrames `0.7.63`。
- `scripts/init_video.sh` 同时兼容 macOS/Linux 的 inode 读取；其他平台必须先运行冒烟测试。
- `review_gen` 从已确认的关键帧工程和时间线开始，不会自动决定叙事、设计特效或替用户通过确认门。
- HyperFrames 使用固定已验证版本；升级前先跑兼容性测试，不自动追随 npm 最新版。

## 验证 · Validation

```bash
python3 tests/validate_skill.py
bash tests/smoke_test.sh
```

冒烟测试生成临时视频和BGM，验证初始化、混音、`-14±0.3 LUFS`、AAC 48kHz双声道以及敏感信息边界，不使用真实媒体或API Key。

## License

MIT — © azu-video-cut contributors（见 LICENSE 文件）
