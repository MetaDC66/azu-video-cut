"""设计系统常量（口播知识短视频审片合成 · 单一事实来源）。

数值来源：工作流固定规则与历次检查器实测沉淀（详见 references/workflow.md）。
任何新视频不改这里，改对应 JSON 或 style_overrides。
"""

# ---- 输出 ----
WIDTH = 1920
HEIGHT = 1080

# ---- 覆盖层 ----
OVERLAY_OPACITY = 0.9            # .fg 整体 90% 不透明度（固定规则）
GLOW_OPACITY = 0.27              # .glow 进入终态
EXIT_FADE_S = 0.42               # .fg 退出淡化时长（v2 规则：场景结束前 0.42s 起）

# ---- 字幕（字幕在所有覆盖层之后最后合成，底部 154px 安全区）----
CAPTION_FONT_FAMILY = "Noto Sans JP"
CAPTION_FONT_WEIGHT = 700
CAPTION_FONT_SIZE_PX = 62        # 单行
CAPTION_FONT_SIZE_LONG_PX = 57   # 两行/长句（display_length > 20）
CAPTION_COLOR = "#fff8ea"        # 暖白
CAPTION_BG = "rgba(8,10,14,.82)" # 82% 深底
CAPTION_BOTTOM_PX = 82           # bottom margin；82 + 最小高 ~72 ≈ 154px 安全区
CAPTION_SAFE_ZONE_PX = 154
CAPTION_LONG_THRESHOLD = 20      # display_length 超过即按长句处理

# ---- 提亮强调色（Session 31 检查器建议值收敛；红采用 90% 透明叠加下实测更安全的 #ef8a85）----
COLOR_BLUE = "#6dafff"
COLOR_RED = "#ef8a85"
COLOR_AMBER = "#f4c161"

# ---- 字幕高亮（合成层类名配色，与字幕 JSON style 段对应）----
CAPTION_ACCENT = "#f2b84b"       # .accent
CAPTION_RISK = "#ef514a"         # .risk

# ---- 缓动规则 ----
# 场景进入（沿用第四条现行参数：分层缓入，power2/power3 组合）
EASE_ENTER = {
    "topline": {"dur": 0.48, "ease": "power2.out", "at": 0.06, "from": {"opacity": 0, "y": -22}},
    "hero":    {"dur": 0.72, "ease": "power3.out", "at": 0.12, "from": {"opacity": 0, "x": 42}},
    "glow":    {"dur": 1.10, "ease": "power2.out", "at": 0.12, "from": {"opacity": 0, "scale": 0.88}},
    "reveal":  {"dur": 0.62, "ease": "power3.out", "at": 0.28, "stagger": 0.07,
                "from": {"opacity": 0, "y": 26, "scale": 0.97}},
}
# 退出：0.42s sine.in 淡化 + tl.set 硬清除（gsap_exit_missing_hard_kill 规则）
EASE_EXIT = {"dur": EXIT_FADE_S, "ease": "sine.in"}

# 字幕进入/退出时长（按时长自适应，上下限钳制）
CAPTION_TWEEN = {
    "enter_min": 0.18, "enter_max": 0.34, "enter_ratio": 0.12,
    "exit_min": 0.08, "exit_max": 0.12, "exit_ratio": 0.06,
}

# ---- 轨道分配 ----
TRACK_MASTER = 0
TRACK_SCREENREC = 1              # master 之上、场景之下（宿主根直接子元素）
TRACK_SCENE = 2
TRACK_CAPTION = 3
TRACK_AUDIO = 10

HYPERFRAMES_VERSION = "0.7.63"
