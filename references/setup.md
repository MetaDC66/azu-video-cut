# 首次配置向导（SETUP）

> 给第一次拿到这个工作流的 Agent：**开工前必须先走完本文件的自检与配置引导**。
> 执行方式：逐项自检 → 缺的项用人话引导用户配置 → 全部 ✅ 后才允许进入 WORKFLOW.md 的流程。
> ⚠️ 安全红线：本包不包含任何 API Key。Agent不得要求用户在对话中发送密钥，不得读取、复制或回显密钥内容。用户只在自己的终端或本地配置文件中填写；Agent只检查变量是否存在、文件权限是否合理和测试是否通过。

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

## 第二步：转录 API Key（用户本机配置，Agent不接触密钥）

词级转录（ElevenLabs Scribe 或 whisper）需要一个 Key。引导流程：

1. 只检查是否已配置，不打印值：`test -n "${ELEVENLABS_API_KEY:-}"`，或检查用户指定的本地 `.env` 文件是否存在；不要运行会输出变量内容的命令。
2. 若缺失，引导用户自己在本机完成以下任一种操作：
   - 在终端交互式设置环境变量；或
   - 复制仓库的 `.env.example` 到转录工具约定的私有配置目录，并用本地编辑器填写。
3. 提醒用户把 `.env` 权限设为仅本人可读写（macOS/Linux：`chmod 600 /path/to/.env`），并确认该路径已被 `.gitignore` 排除。
4. Agent只报告“已配置/未配置”和权限检查结果，不读取文件正文，不显示任何前缀或后缀。
5. 用一条5秒测试音频验证服务可用；测试日志不得包含认证请求头或密钥。
6. 若用户不想使用云端转录，fallback到本地whisper或whisper.cpp，并说明速度、模型体积和词级时间戳差异。

## 第三步：品牌资产个性化（必问用户）

包里的品牌元素属于原作者，新用户必须替换成自己的。逐项引导：

| 项 | 引导问题 | 落点 |
|---|---|---|
| 频道名 | 「你的频道/账号名叫什么？」 | 替换品牌收尾卡文案、封面角标文字 |
| 品牌角标 | 「有 Logo 或角标图吗？发我 PNG（透明底最好），没有的话我按频道名帮你生成一个文字版角标。」 | `edit/brand/<频道名>-角标.png`，沿用规范：左上、宽 330px、留边 28px、PIL 后期合成 |
| 口播收尾语 | 「你的固定收尾口播是什么？（用于触发片尾品牌卡，例：『我是<频道名>，下期再见』）」 | 写入 WORKFLOW.md 第 2 阶段收尾模板 |
| 出镜参考照 | 「发一张你的出镜照（封面用，清晰正面、手势自然）。不想真人出镜的话告诉我，封面改成纯文字+图形风格。」 | `edit/cover/work/` |
| 设计色板（可选） | 「想沿用蓝黑科技风，还是有自己的品牌色？」 | 改 `scripts/review_gen/defaults.py` |

## 第四步：建立非敏感项目配置

将 `templates/project-profile.json` 复制到用户项目根的 `project-profile.json`，填写频道名、平台、收尾语、角标、BGM、字体和输出规格。该文件不得包含密钥、Cookie、账号或私人绝对路径。

已有配置时只检查缺项，不重复询问已经确认的信息。

## 第五步：素材与规范确认（快速确认即可）

- BGM：包内 `edit/bgm-library/` 若为空，引导用户选一条明亮轻快无版权 BGM 入库，记入 README 选曲约束（禁小调压迫/暗色悬疑/渐强/重低频）。
- 发布平台：确认目标平台（抖音/B站/视频号…），影响封面比例与发布自查项。
- 字体：确认系统有 `Noto Sans JP` 700（中文回退 PingFang SC），缺则引导安装。

## 第六步：开工验证（工程生成到混音的冒烟测试）

全部配置完成后，跑一遍最小验证，一项不过就不开工：

1. `bash scripts/init_video.sh test-video /path/to/任意短测试视频.mp4 --out-dir /tmp/azu-video-cut-smoke` 成功输出一行 JSON
2. 用测试视频跑通 `python3 scripts/review_gen/generate.py` 的工程生成；具备HyperFrames运行环境时再执行 `--check`（0 error）
3. `mix_finalize.py` 在测试视频上混音达标（-14±0.3 LUFS / ≤-1.5 dBTP）
4. 验证产物为 H.264、AAC 48kHz双声道，响度达到 `-14±0.3 LUFS / ≤-1.5 dBTP`。
5. 清理测试目录，向用户报告：「配置完成，把第一条初剪母版发我就能开工。」
