---
name: azu-video-cut
description: 短视频剪辑管线：选题→口播稿→精剪→封面→发布。当用户要剪辑口播视频、做字幕覆盖层、混音收口、出发布成片时使用
---

# azu-video-cut · 口播知识短视频剪辑管线

## 首次运行检测（开工前必做）

逐项自检，任一缺失就先引导用户走 `references/setup.md` 的五步配置，全部就位才允许开工：

1. 环境：ffmpeg / ffprobe / python3 / node+npx（22+）/ PIL
2. 转录 API Key 已写入本机 `.env`（或用户确认走本地 whisper fallback）
3. 品牌资产已个性化：频道名、角标 PNG、口播收尾语、出镜参考照（包内无任何品牌资产，必须用用户自己的）
4. BGM 已入库（包内不含音乐文件；`--mix` 必须 `--bgm` 显式传入）
5. 冒烟测试通过（setup.md 第五步：脚手架 + check + 混音达标）

## 四道硬性确认门（不得跳过）

| 门 | 确认内容 | 未确认前禁止 |
|---|---|---|
| G1 选题门 | 选题 + 唯一承诺一句话 | 不写稿 |
| G2 稿件门 | 口播稿逐字确认（稿件=权威文本） | 不动工 |
| G3 抽检门 | 10 秒抽检样片（带完整声音方案） | 不渲染全片 |
| G4 发布门 | 完整审片版通看 + 封面文字逐字确认 | 不出交付版/封面图 |

## 一页速查

```
剪辑顺序：脚手架开工 → 素材核验 → 转录+名词确认 → 字幕时间线(去标点/canon校验) →
         覆盖层槽位 → 关键帧静帧审 → BGM确认 → 10s抽检(带完整混音) →
         全片审片版(响度按全片重算) → 高码率交付版 → 封面(先文字后图) → 发布自查
硬性数字：-14±0.3 LUFS / ≤-1.5 dBTP / 字幕无标点 / 覆盖层90% /
         Noto Sans JP 700 / 蓝#6dafff 红#ef8a85 amber#f4c161 /
         封面 1086×1448 / 角标左上330px留边28px
永不：跳过确认门 / 覆盖旧版本 / 让AI画角标 / 照抄抽检响度参数 / 把API Key写进对话或分享文件
```

## Skill 路由表（按需读取，省 token）

| 任务 | 入口 |
|---|---|
| 完整流程与规则细节 | `references/workflow.md` |
| 首次配置引导（环境/Key/品牌/BGM/冒烟） | `references/setup.md` |
| 每条视频全程勾选项 | `references/checklist.md` |
| 封面规范与提示词骨架 | `references/cover-style-guide.md` |
| 开工脚手架（建目录/master.json/骨架） | `scripts/init_video.sh 第N条 /path/to/母版.mov` |
| 审片端到端（工程→check→渲染→混音） | `scripts/review_gen/generate.py --check --render --mix --bgm <音乐>` |
| 混音收口（单用） | `scripts/mix_finalize.py --video X --bgm Y --out Z` |
| 选题 | `templates/topic-card.md` |
| 复盘回流 | `templates/publish-log.md` |
| 三份 JSON 骨架 | `templates/master.json` / `subtitle-timeline.json` / `overlay-timeline.json` |

> 脚本路径均相对本 skill 目录。脚本若引用 `bgm-library`、`<N>-master/` 等目录，均相对用户工作区，首次使用按 setup.md 建立。新增场景类型：在 `scripts/review_gen/hooks.py` 注册钩子，不动主流程。
