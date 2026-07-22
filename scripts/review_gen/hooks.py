"""场景类型钩子注册表（hook registry）。

主流程按 overlay-timeline.json 每个 scene 的 `type` 字段分发到这里；
新增场景类型 = 在下面加一个钩子函数并注册进 HOOKS，不动主流程。

每个钩子可提供四个可选方法（缺省即 generic 行为）：
  extra_nodes(scene, ctx) -> str   注入宿主根直接子元素（如录屏 <video> 层）
  set(sid) -> str                  t=0 压为不可见的额外元素（防闪屏 set 同步带上）
  enter(sid, st) -> str            程序化元素的进入动效（接在标准进入链后）
  hold(sid) -> str                 窗口起点已激活时直接置终态的额外元素
ctx 字段：win_start, win_end, win_dur, local_start, local_end
"""
from __future__ import annotations

import defaults as D


class GenericHook:
    """标准 GSAP 场景：防闪屏（t=0 set + fromTo 接管）与 .fg 退出硬清除都在主流程处理。"""

    def extra_nodes(self, scene: dict, ctx: dict) -> str:
        return ""

    def set(self, sid: str) -> str:
        return ""

    def enter(self, sid: str, st: float) -> str:
        return ""

    def hold(self, sid: str) -> str:
        return ""


class MagnifierHook(GenericHook):
    """放大镜场景（.mag/.mag-tag 程序化弹入 + 标签）。"""

    def set(self, sid: str) -> str:
        return f'\n  .set("#{sid} .mag, #{sid} .mag-tag", {{ opacity: 0 }}, 0)'

    def enter(self, sid: str, st: float) -> str:
        return (
            f'\n  .fromTo("#{sid} .mag", {{ opacity: 0, scale: .35 }}, {{ opacity: 1, scale: 1, duration: .5, ease: "back.out(2.2)", immediateRender: false }}, {st + .38:.3f})'
            f'\n  .fromTo("#{sid} .mag-tag", {{ opacity: 0, y: 14 }}, {{ opacity: 1, y: 0, duration: .34, ease: "power2.out", immediateRender: false }}, {st + .62:.3f})'
        )

    def hold(self, sid: str) -> str:
        return f'\n  .set("#{sid} .mag, #{sid} .mag-tag", {{ opacity: 1, scale: 1, y: 0 }}, 0)'


class ScreenrecHook(GenericHook):
    """录屏视频层场景：深色侧板 .side 滑入 + 录屏 <video> 单独重定时注入。

    HyperFrames 媒体规则：<video> 必须是宿主根直接子元素（extract 不会带出），
    track = TRACK_SCREENREC（master 之上、场景之下），muted playsinline，
    data-media-start 对窗口偏移。
    """

    def extra_nodes(self, scene: dict, ctx: dict) -> str:
        src = scene.get("video", "assets/screenrec.mp4")
        media_offset = max(0.0, ctx["win_start"] - scene["start"])
        dur = ctx["local_end"] - ctx["local_start"]
        return (
            f'      <video id="screenrec" class="clip" src="{src}" '
            f'data-start="{ctx["local_start"]:.3f}" data-duration="{dur:.3f}" '
            f'data-media-start="{media_offset:.3f}" data-track-index="{D.TRACK_SCREENREC}" muted playsinline></video>'
        )

    def set(self, sid: str) -> str:
        return f'\n  .set("#{sid} .side", {{ opacity: 0 }}, 0)'

    def enter(self, sid: str, st: float) -> str:
        return (
            f'\n  .fromTo("#{sid} .side.left", {{ opacity: 0, x: -120 }}, {{ opacity: 1, x: 0, duration: .5, ease: "power3.out", immediateRender: false }}, {st + .1:.3f})'
            f'\n  .fromTo("#{sid} .side.right", {{ opacity: 0, x: 120 }}, {{ opacity: 1, x: 0, duration: .5, ease: "power3.out", immediateRender: false }}, {st + .1:.3f})'
        )

    def hold(self, sid: str) -> str:
        return f'\n  .set("#{sid} .side", {{ opacity: 1, x: 0 }}, 0)'


class BrandCardHook(GenericHook):
    """品牌收尾卡：现行无自定义程序化动效（badge/headline 走标准 .reveal/.hero 链）。"""


HOOKS = {
    "generic": GenericHook(),
    "magnifier": MagnifierHook(),
    "screenrec": ScreenrecHook(),
    "brand_card": BrandCardHook(),
}


def resolve(scene: dict) -> GenericHook:
    """按 scene['type'] 取钩子；未知类型回退 generic 并由调用方记录告警。"""
    return HOOKS.get(scene.get("type", "generic"), HOOKS["generic"])
