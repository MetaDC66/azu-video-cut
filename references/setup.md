# 首次配置向导（SETUP）

> 给第一次拿到这个工作流的 Agent：**开工前必须先走完本文件的自检与配置引导**。
> 执行方式：逐项自检 → 缺的项用人话引导用户配置 → 全部 ✅ 后才允许进入 WORKFLOW.md 的流程。
> ⚠️ 安全红线：本包不包含任何 API Key。配置过程中用户粘贴的 Key 只写入本机 `.env` 文件，**绝不写进对话输出、不写进工作区任何会被分享的 md/json/sh 文件、不提交到 git**。

---

## 第一步：环境依赖自检（Agent 自动跑，无需问用户）

逐项检查，缺的标记出来：

```bash
which ffmpeg ffprobe        # 剪辑/混音/验证全链路依赖
which python3               # 工具脚本运行
which node npm npx          # HyperFrames 覆盖层渲染（需 Node 22+）
python3 -c "import PIL"     # 封面角标合成
```

| 缺失项 | 引导话术与动作 |
|---|---|
| ffmpeg | 「剪辑全链路需要 ffmpeg，要我帮你装吗？」（macOS: `brew install ffmpeg`） |
| Node | 「覆盖层渲染需要 Node.js 22+，要我帮你装吗？」 |
| hyperframes | 首次用到时在 slot 目录内 `npx --yes hyperframes init` 即可，不全局安装 |
| PIL | `pip install pillow` |

## 第二步：转录 API Key（引导用户配置，不代填）

词级转录（ElevenLabs Scribe 或 whisper）需要一个 Key。引导流程：

1. 先检测：`env | grep -i ELEVENLABS` 或当前转录 skill 的本地 `.env` 是否已存在。
2. 若缺失，对用户说：
   > 「转录需要 ElevenLabs API Key。请到 elevenlabs.io 后台复制你的 Key 发给我，我只会写入本机配置文件，不会出现在任何对话记录和分享文件里。没有账号的话现在注册一个，免费额度够试几条视频。」
3. 用户发来后：写入当前转录 skill 的本地 `.env`（或用户指定的本地配置位置），**回显时脱敏**（只显示前 4 位 + `...`）。
4. 用一条 5 秒测试音频验证 Key 可用，再标记 ✅。
5. 若用户不想用 ElevenLabs：fallback 到本地 whisper（需 `pip install openai-whisper` 或 whisper.cpp），在 WORKFLOW.md 允许范围内，告诉用户精度差异（whisper 无词级时间戳时需用 DTW 对齐，本管线已有先例）。

## 第三步：品牌资产个性化（必问用户）

包里的品牌元素属于原作者，新用户必须替换成自己的。逐项引导：

| 项 | 引导问题 | 落点 |
|---|---|---|
| 频道名 | 「你的频道/账号名叫什么？」 | 替换品牌收尾卡文案、封面角标文字 |
| 品牌角标 | 「有 Logo 或角标图吗？发我 PNG（透明底最好），没有的话我按频道名帮你生成一个文字版角标。」 | `edit/brand/<频道名>-角标.png`，沿用规范：左上、宽 330px、留边 28px、PIL 后期合成 |
| 口播收尾语 | 「你的固定收尾口播是什么？（用于触发片尾品牌卡，例：『我是<频道名>，下期再见』）」 | 写入 WORKFLOW.md 第 2 阶段收尾模板 |
| 出镜参考照 | 「发一张你的出镜照（封面用，清晰正面、手势自然）。不想真人出镜的话告诉我，封面改成纯文字+图形风格。」 | `edit/cover/work/` |
| 设计色板（可选） | 「想沿用蓝黑科技风，还是有自己的品牌色？」 | 改 `scripts/review_gen/defaults.py` |

## 第四步：素材与规范确认（快速确认即可）

- BGM：包内 `edit/bgm-library/` 若为空，引导用户选一条明亮轻快无版权 BGM 入库，记入 README 选曲约束（禁小调压迫/暗色悬疑/渐强/重低频）。
- 发布平台：确认目标平台（抖音/B站/视频号…），影响封面比例与发布自查项。
- 字体：确认系统有 `Noto Sans JP` 700（中文回退 PingFang SC），缺则引导安装。

## 第五步：开工验证（端到端冒烟测试）

全部配置完成后，跑一遍最小验证，一项不过就不开工：

1. `scripts/init_video.sh 测试 /path/to/任意短测试视频.mp4` 成功输出一行 JSON
2. 用测试视频跑通 `review_gen/generate.py --check`（0 error）
3. `mix_finalize.py` 在测试视频上混音达标（-14±0.3 LUFS / ≤-1.5 dBTP）
4. 清理测试目录，向用户报告：「配置完成，把第一条初剪母版发我就能开工。」
