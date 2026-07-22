#!/usr/bin/env python3
"""review_gen/generate.py — 三份 JSON 驱动的审片合成与交付生成器。

输入：
  --master     master.json      母版路径 / fps / 时长 / 可选 expected_inode / style_overrides
  --subtitles  subtitle-timeline.json   cues + 可选 highlight.accent / highlight.risk 词表
  --overlay    overlay-timeline.json    场景槽位；每个 scene 必须有 type 字段（hooks.py 注册表）
  --keyframes  关键帧工程目录（含 index.html / hyperframes.json / assets/）

阶段（每个阶段只打印一行 JSON 进度/结论，失败即停并打印失败阶段与首条错误）：
  generate  生成 HyperFrames 工程（母版强制 unlink 重链 + samefile/inode 断言）
  check     --check：hyperframes check 一行摘要
  render    --render：标准质量渲染；预计超单次上限时按「场景间纯母版空档 +
            字幕空档 + 帧对齐」自动选分段点分段渲染 + ffmpeg -c copy 无损拼接
  mix       --mix：调用 ../mix_finalize.py 混音收口（BGM 需用 --bgm 显式传入，
            --voice-i 可覆盖人声目标，含长静音段窗口用 -13.2）

从已确认关键帧工程到交付的用法：
  python3 generate.py --master master.json --subtitles subtitle-timeline.json \
      --overlay overlay-timeline.json --keyframes <N>-master/hyperframes-keyframes \
      --start 10 --end 20 --name review-sample-10-20 --title "第N条·10至20秒抽检" \
      --out-dir . --check --render --mix --voice-i -13.2
"""
from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import defaults as D
import hooks as H

SKILL_SCRIPTS = Path(__file__).resolve().parent.parent       # scripts/
MIX_FINALIZE = SKILL_SCRIPTS / "mix_finalize.py"

# 预计渲染耗时模型：frames/20fps + 20s 启动；超 SINGLE_RUN_BUDGET_S 即分段
SINGLE_RUN_BUDGET_S = 250


def jline(stage: str, **kw) -> None:
    """阶段一行 JSON 输出（省 token）。"""
    print(json.dumps({"stage": stage, **kw}, ensure_ascii=False))


def fail(stage: str, err: str) -> None:
    jline(stage, ok=False, error=err.strip().splitlines()[-1][:300] if err.strip() else "unknown")
    sys.exit(1)


# ---------- 字幕 ----------

def display_length(text: str) -> int:
    latin_groups = re.findall(r"[A-Za-z0-9%]+(?: [A-Za-z0-9%]+)*", text)
    without_latin = re.sub(r"[A-Za-z0-9%]+(?: [A-Za-z0-9%]+)*", "", text)
    return len(without_latin) + sum(max(2, round(len(g) * 0.55)) for g in latin_groups)


def styled_text(text: str, risk_terms, accent_terms) -> str:
    matches: list[tuple[int, int, str]] = []
    for css_class, terms in (("risk", risk_terms), ("accent", accent_terms)):
        for term in terms:
            start = text.find(term)
            if start >= 0:
                matches.append((start, start + len(term), css_class))
    selected: list[tuple[int, int, str]] = []
    for m in sorted(matches, key=lambda i: (i[0], -(i[1] - i[0]))):
        if any(m[0] < e and m[1] > s for s, e, _ in selected):
            continue
        selected.append(m)
    pieces, cursor = [], 0
    for start, end, css_class in sorted(selected):
        pieces.append(html.escape(text[cursor:start]))
        pieces.append(f'<span class="{css_class}">{html.escape(text[start:end])}</span>')
        cursor = end
    pieces.append(html.escape(text[cursor:]))
    return "".join(pieces)


# ---------- 关键帧工程提取 ----------

def extract_keyframes(keyframes_html: Path) -> tuple[str, dict[str, str]]:
    source = keyframes_html.read_text(encoding="utf-8")
    style = re.search(r"<style>(.*?)</style>", source, re.S).group(1)
    scene_map: dict[str, str] = {}
    for full, scene_id in re.findall(r'(<section id="(scene-\d+)".*?</section>)', source, re.S):
        body = re.sub(r'<img class="bg"[^>]*>', "", full, count=1)
        scene_map[scene_id] = body.strip()
    return style, scene_map


def retime_scene(section: str, start: float, duration: float) -> str:
    section = re.sub(r'data-start="[^"]*"', f'data-start="{start:.3f}"', section, count=1)
    section = re.sub(r'data-duration="[^"]*"', f'data-duration="{duration:.3f}"', section, count=1)
    section = re.sub(r'data-track-index="[^"]*"', f'data-track-index="{D.TRACK_SCENE}"', section, count=1)
    # 两行大标题字体边界误报：标记为有意堆叠（同前作处理）
    if '<h1 class="headline hero">' in section:
        section = section.replace('<h1 class="headline hero">', '<h1 class="headline hero" data-layout-allow-overlap>')
    return section


# ---------- 阶段：check ----------

def run_check(out_dir: Path) -> None:
    r = subprocess.run(
        ["npx", "--yes", f"hyperframes@{D.HYPERFRAMES_VERSION}", "check"],
        cwd=out_dir, capture_output=True, text=True)
    text = r.stdout + r.stderr
    m = re.search(r"(\d+)\s+errors?\b", text, re.I)
    n_err = int(m.group(1)) if m else 0
    m = re.search(r"(\d+)\s+warnings?\b", text, re.I)
    n_warn = int(m.group(1)) if m else 0
    first_err = ""
    for line in text.splitlines():
        if re.search(r"\berror\b", line, re.I) and not re.search(r"\d+\s+errors?\b", line, re.I):
            first_err = line.strip()[:200]
            break
    ok = n_err == 0 and r.returncode == 0
    jline("check", ok=ok, errors=n_err, warnings=n_warn,
          **({"first_error": first_err} if first_err else {}))
    if not ok:
        sys.exit(1)


# ---------- 阶段：generate ----------

def build_project(cfg: dict, win_start: float, win_end: float,
                  name: str, title: str, out_parent: Path) -> Path:
    win_dur = win_end - win_start
    style = cfg["style"]
    scene_map = cfg["scene_map"]
    overlay = cfg["overlay"]
    subtitles = cfg["subtitles"]
    kf_root = cfg["kf_root"]
    fps = cfg["fps"]

    # ---- 窗口内场景 ----
    scene_nodes: list[str] = []
    timeline_parts: list[str] = []
    extra_nodes: list[str] = []
    unknown_types: list[str] = []
    for scene in overlay["scenes"]:
        s0, s1 = scene["start"], scene["end"]
        if s1 <= win_start or s0 >= win_end:
            continue
        stype = scene.get("type", "generic")
        hook = H.resolve(scene)
        if stype not in H.HOOKS:
            unknown_types.append(f'{scene["id"]}:{stype}')
        local_start = max(0.0, s0 - win_start)
        local_end = min(win_dur, s1 - win_start)
        sid = scene["id"]
        scene_nodes.append(retime_scene(scene_map[sid], local_start, local_end - local_start))

        node = hook.extra_nodes(scene, {
            "win_start": win_start, "win_end": win_end, "win_dur": win_dur,
            "local_start": local_start, "local_end": local_end})
        if node:
            extra_nodes.append(node)

        if s0 <= win_start + 0.05:
            hold = (
                f'tl.set("#{sid} .topline, #{sid} .hero, #{sid} .reveal", {{ opacity: 1, x: 0, y: 0, scale: 1 }}, 0)\n'
                f'  .set("#{sid} .glow", {{ opacity: .27, scale: 1 }}, 0)')
            hold += hook.hold(sid)
            timeline_parts.append(hold)
        else:
            st = local_start
            # 防闪屏：进入动画开始前 t=0 先把进入元素压为不可见
            enter = (
                f'tl.set("#{sid} .topline, #{sid} .hero, #{sid} .reveal", {{ opacity: 0 }}, 0)\n'
                f'  .set("#{sid} .glow", {{ opacity: 0 }}, 0)')
            enter += hook.set(sid)
            enter += (
                f'\n  .fromTo("#{sid} .topline", {{ opacity: 0, y: -22 }}, {{ opacity: 1, y: 0, duration: .48, ease: "power2.out", immediateRender: false }}, {st + .06:.3f})\n'
                f'  .fromTo("#{sid} .hero", {{ opacity: 0, x: 42 }}, {{ opacity: 1, x: 0, duration: .72, ease: "power3.out", immediateRender: false }}, {st + .12:.3f})\n'
                f'  .fromTo("#{sid} .glow", {{ opacity: 0, scale: .88 }}, {{ opacity: .27, scale: 1, duration: 1.1, ease: "power2.out", immediateRender: false }}, {st + .12:.3f})\n'
                f'  .fromTo("#{sid} .reveal", {{ opacity: 0, y: 26, scale: .97 }}, {{ opacity: 1, y: 0, scale: 1, duration: .62, stagger: .07, ease: "power3.out", immediateRender: false }}, {st + .28:.3f})')
            enter += hook.enter(sid, st)
            timeline_parts.append(enter)
        # .fg 退出淡化（结束前 0.42s）+ tl.set 硬清除（gsap_exit_missing_hard_kill）
        if s1 < win_end - 0.05:
            exit_at = local_end - D.EXIT_FADE_S
            timeline_parts.append(
                f'tl.to("#{sid} .fg", {{ opacity: 0, duration: .42, ease: "sine.in", immediateRender: false }}, {exit_at:.3f})\n'
                f'  .set("#{sid} .fg", {{ opacity: 0 }}, {local_end:.3f})')

    # ---- 窗口内字幕 ----
    caption_nodes: list[str] = []
    cues_js: list[dict] = []
    for cue in subtitles["cues"]:
        if cue["end"] <= win_start or cue["start"] >= win_end:
            continue
        local_start = max(0.0, cue["start"] - win_start)
        local_end = min(win_dur, cue["end"] - win_start)
        index = len(cues_js)
        long_class = " long" if display_length(cue["text"]) > D.CAPTION_LONG_THRESHOLD else ""
        caption_nodes.append(
            f'<div id="cg-{index}" class="caption-group{long_class}"><div class="caption-shell">{styled_text(cue["text"], cfg["risk_terms"], cfg["accent_terms"])}</div></div>')
        cues_js.append({"start": round(local_start, 3), "end": round(local_end, 3)})

    # ---- 工程脚手架 ----
    out = out_parent / name
    (out / "assets" / "evidence").mkdir(parents=True, exist_ok=True)
    (out / "outputs").mkdir(exist_ok=True)
    master_video = cfg["master_video"]
    master_link = out / "assets" / "master.mov"
    # 总是重链：防止母版换版后沿用旧硬链接（Session 28 根因）
    if master_link.exists():
        master_link.unlink()
    try:
        master_link.hardlink_to(master_video)
    except OSError:
        shutil.copy2(master_video, master_link)
    assert master_link.samefile(master_video), "master link 与母版路径不一致"
    if cfg["expected_inode"] is not None:
        actual = master_link.stat().st_ino
        assert actual == cfg["expected_inode"], (
            f"inode 不符: {actual} != 预期 {cfg['expected_inode']}（疑似母版换版）")

    # 资产：录屏视频 / 证据截图 / 品牌角标 / hyperframes.json
    for scene in overlay["scenes"]:
        vid = scene.get("video")
        if vid:
            src = kf_root / "assets" / Path(vid).name
            dest = out / "assets" / Path(vid).name
            if src.exists() and not dest.exists():
                shutil.copy2(src, dest)
    for sub in ("evidence", "brand"):
        src_dir = kf_root / "assets" / sub
        if src_dir.is_dir():
            (out / "assets" / sub).mkdir(parents=True, exist_ok=True)
            for img in src_dir.iterdir():
                dest = out / "assets" / sub / img.name
                if img.is_file() and not dest.exists():
                    shutil.copy2(img, dest)
    shutil.copy2(kf_root / "hyperframes.json", out / "hyperframes.json")
    (out / "caption-overrides.json").write_text("[]", encoding="utf-8")
    (out / "package.json").write_text(json.dumps({
        "name": name, "private": True, "type": "module",
        "scripts": {
            "dev": f"npx --yes hyperframes@{D.HYPERFRAMES_VERSION} preview",
            "check": f"npx --yes hyperframes@{D.HYPERFRAMES_VERSION} check",
            "render": f"npx --yes hyperframes@{D.HYPERFRAMES_VERSION} render",
        },
    }, indent=2), encoding="utf-8")

    caption_css = f"""
      #master-video {{ position: absolute; inset: 0; width: {D.WIDTH}px; height: {D.HEIGHT}px; object-fit: cover; }}
      .caption-layer {{ position: absolute; inset: 0; width: 100%; height: 100%; overflow: visible; z-index: 20; }}
      .caption-group {{ position: absolute; z-index: 21; left: 0; right: 0; bottom: {D.CAPTION_BOTTOM_PX}px; min-height: 90px; display: flex; justify-content: center; align-items: flex-end; padding: 0 96px; opacity: 0; visibility: hidden; overflow: visible; }}
      .caption-shell {{ display: block; max-width: 1382px; min-height: 90px; padding: 16px 30px 20px; border: 1px solid rgba(255,255,255,.12); border-radius: 20px; background: {D.CAPTION_BG}; box-shadow: 0 12px 36px rgba(0,0,0,.42); color: {D.CAPTION_COLOR}; font-family: "{D.CAPTION_FONT_FAMILY}", sans-serif; font-size: {D.CAPTION_FONT_SIZE_PX}px; font-weight: {D.CAPTION_FONT_WEIGHT}; line-height: 1.24; letter-spacing: -.035em; text-align: center; text-wrap: balance; text-shadow: 0 2px 5px rgba(0,0,0,.75); overflow: visible; }}
      .caption-group.long .caption-shell {{ max-width: 1440px; font-size: {D.CAPTION_FONT_SIZE_LONG_PX}px; padding-left: 34px; padding-right: 34px; }}
      .caption-shell .accent {{ color: {D.CAPTION_ACCENT}; }}
      .caption-shell .risk {{ color: {D.CAPTION_RISK}; }}
    """

    cues_json = json.dumps(cues_js, ensure_ascii=False)
    caption_tween = """
      CUES.forEach((cue, index) => {
        const target = `#cg-${index}`;
        const duration = cue.end - cue.start;
        const enterDuration = Math.min(.34, Math.max(.18, duration * .12));
        const exitDuration = Math.min(.12, Math.max(.08, duration * .06));
        tl.set(target, { visibility: "visible", opacity: 0, y: 22, scale: .985 }, cue.start);
        tl.to(target, { opacity: 1, y: 0, scale: 1, duration: enterDuration, ease: "power3.out" }, cue.start);
        tl.to(target, { opacity: 0, y: -8, scale: .99, duration: exitDuration, ease: "power2.in" }, Math.max(cue.start + enterDuration, cue.end - exitDuration));
        tl.set(target, { opacity: 0, visibility: "hidden" }, cue.end);
      });
    """

    scenes_html = "\n".join(scene_nodes)
    captions_html = "".join(caption_nodes)
    timeline_js = "\n".join(timeline_parts)
    extras_html = "\n".join(extra_nodes)

    document = f"""<!doctype html>
<html lang="zh-CN" data-resolution="landscape">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={D.WIDTH}, height={D.HEIGHT}" />
    <title>{title}</title>
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>{style}
      :root {{ --blue: {cfg["color_blue"]}; --red: {cfg["color_red"]}; --amber: {cfg["color_amber"]}; }}
      .headline {{ line-height: 1.08; }}
      {caption_css}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="{name}" data-start="0" data-duration="{win_dur:.3f}" data-width="{D.WIDTH}" data-height="{D.HEIGHT}" data-fps="{fps}">
      <video id="master-video" class="clip" src="assets/master.mov" data-start="0" data-duration="{win_dur:.3f}" data-media-start="{win_start:.3f}" data-track-index="{D.TRACK_MASTER}" muted playsinline></video>
      <audio id="master-audio" src="assets/master.mov" data-start="0" data-duration="{win_dur:.3f}" data-media-start="{win_start:.3f}" data-track-index="{D.TRACK_AUDIO}" data-volume="1"></audio>
{extras_html}
{scenes_html}
      <section id="caption-layer" class="clip caption-layer" data-start="0" data-duration="{win_dur:.3f}" data-track-index="{D.TRACK_CAPTION}">
        {captions_html}
      </section>
    </div>
    <script>
      window.__timelines = window.__timelines || {{}};
      const CUES = {cues_json};
      const tl = gsap.timeline({{ paused: true }});

      {timeline_js}
      {caption_tween}

      window.__timelines["{name}"] = tl;
    </script>
  </body>
</html>
"""
    (out / "index.html").write_text(document, encoding="utf-8")
    jline("generate", ok=True, project=str(out), window=f"{win_start}-{win_end}",
          duration_s=round(win_dur, 3), scenes=len(scene_nodes), captions=len(cues_js),
          extra_layers=len(extra_nodes),
          **({"unknown_type_fallback": unknown_types} if unknown_types else {}))
    return out


# ---------- 阶段：render ----------

def find_split_point(overlay: dict, subtitles: dict,
                     win_start: float, win_end: float, fps: int) -> float | None:
    """分段点三重条件：场景间纯母版空档 + 字幕空档 + 帧对齐；取最接近窗口中点者。"""
    scene_spans = sorted((s["start"], s["end"]) for s in overlay["scenes"])
    cue_spans = sorted((c["start"], c["end"]) for c in subtitles["cues"])

    mid = (win_start + win_end) / 2
    # 候选 = 相邻场景空档与相邻字幕空档的重叠区
    scene_gaps = [(a[1], b[0]) for a, b in zip(scene_spans, scene_spans[1:]) if b[0] - a[1] > 0.2]
    cue_gaps = [(a[1], b[0]) for a, b in zip(cue_spans, cue_spans[1:]) if b[0] - a[1] > 0.1]
    candidates: list[float] = []
    for sg0, sg1 in scene_gaps:
        for cg0, cg1 in cue_gaps:
            lo, hi = max(sg0, cg0), min(sg1, cg1)
            lo = max(lo, win_start + 1.0)
            hi = min(hi, win_end - 1.0)
            if hi - lo < 2.0 / fps + 0.04:
                continue
            # 取重叠空档中点并帧对齐，须留 0.02s 余量不贴边界
            t_frame = round(((lo + hi) / 2) * fps) / fps
            if lo + 0.02 <= t_frame <= hi - 0.02:
                candidates.append(t_frame)
    if not candidates:
        return None
    return min(candidates, key=lambda t: abs(t - mid))


def render_one(project: Path) -> Path:
    before = set((project / "renders").glob("*.mp4")) if (project / "renders").is_dir() else set()
    r = subprocess.run(["npx", "--yes", f"hyperframes@{D.HYPERFRAMES_VERSION}", "render"],
                       cwd=project, capture_output=True, text=True)
    if r.returncode != 0:
        fail("render", r.stderr or r.stdout)
    new = sorted(set((project / "renders").glob("*.mp4")) - before,
                 key=lambda p: p.stat().st_mtime)
    if not new:
        fail("render", "渲染结束但未找到产物 renders/*.mp4")
    return new[-1]


def ffprobe_video(path: Path) -> tuple[int, float]:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=nb_frames:format=duration",
         "-of", "json", str(path)], capture_output=True, text=True)
    info = json.loads(r.stdout)
    frames = int(info["streams"][0].get("nb_frames", 0))
    return frames, float(info["format"]["duration"])


def run_render(cfg: dict, win_start: float, win_end: float,
               name: str, title: str, out_parent: Path) -> Path:
    """返回最终合成（未混音）视频路径 outputs/<name>-video-only.mp4。"""
    fps = cfg["fps"]
    total_frames = round((win_end - win_start) * fps)
    est_s = total_frames / 20 + 20
    final_dir = out_parent / name
    final_dir.mkdir(parents=True, exist_ok=True)
    (final_dir / "outputs").mkdir(exist_ok=True)
    dest = final_dir / "outputs" / f"{name}-video-only.mp4"

    t0 = time.time()
    if est_s <= SINGLE_RUN_BUDGET_S:
        project = build_project(cfg, win_start, win_end, name, title, out_parent)
        if cfg["do_check"]:
            run_check(project)
        video = render_one(project)
        shutil.copy2(video, dest)
        frames, dur = ffprobe_video(dest)
        jline("render", ok=True, segments=1, frames=frames, duration_s=round(dur, 3),
              elapsed_s=round(time.time() - t0, 1), out=str(dest))
        return dest

    # 分段：场景间纯母版空档 + 字幕空档 + 帧对齐
    split = find_split_point(cfg["overlay"], cfg["subtitles"], win_start, win_end, fps)
    if split is None:
        fail("render", "预计超单次渲染上限，但找不到满足三重条件的分段点（场景空档+字幕空档+帧对齐）")
    seg_files: list[Path] = []
    for tag, s, e in (("A", win_start, split), ("B", split, win_end)):
        seg_name = f"{name}-seg{tag}"
        project = build_project(cfg, s, e, seg_name, f"{title}·{tag}段", out_parent)
        if cfg["do_check"]:
            run_check(project)
        seg_files.append(render_one(project))
    concat_list = final_dir / "outputs" / ".concat.txt"
    concat_list.write_text("".join(f"file '{f.resolve()}'\n" for f in seg_files), encoding="utf-8")
    r = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
         "-i", str(concat_list), "-c", "copy", str(dest)],
        capture_output=True, text=True)
    concat_list.unlink()
    if r.returncode != 0:
        fail("render", "分段拼接失败: " + r.stderr)
    frames, dur = ffprobe_video(dest)
    jline("render", ok=True, segments=2, split_at=split, frames=frames,
          duration_s=round(dur, 3), elapsed_s=round(time.time() - t0, 1), out=str(dest))
    return dest


# ---------- 阶段：mix ----------

def run_mix(video: Path, bgm: Path, voice_i: str, out: Path) -> None:
    r = subprocess.run(
        [sys.executable, str(MIX_FINALIZE), "--video", str(video),
         "--bgm", str(bgm), "--out", str(out), "--voice-i", voice_i],
        capture_output=True, text=True)
    line = (r.stdout.strip().splitlines() or [""])[-1]
    try:
        result = json.loads(line)
    except json.JSONDecodeError:
        fail("mix", r.stderr or r.stdout)
    if r.returncode != 0 or not result.get("ok"):
        jline("mix", ok=False, **result)
        sys.exit(1)
    jline("mix", out=str(out), **result)


# ---------- 主流程 ----------

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--master", required=True)
    p.add_argument("--subtitles", required=True)
    p.add_argument("--overlay", required=True)
    p.add_argument("--keyframes", required=True, help="关键帧工程目录（含 index.html）")
    p.add_argument("--start", type=float, required=True)
    p.add_argument("--end", type=float, required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--out-dir", default=".", help="工程输出父目录（name 子目录）")
    p.add_argument("--check", action="store_true", help="生成后运行 hyperframes check（一行摘要）")
    p.add_argument("--render", action="store_true", help="生成后渲染（超上限自动分段拼接）")
    p.add_argument("--mix", action="store_true", help="渲染后调 mix_finalize.py 混音收口")
    p.add_argument("--bgm", default=None,
                   help="BGM 音频文件路径（无默认：首次使用请先按 references/setup.md 第四步配置音乐库）")
    p.add_argument("--voice-i", default="-16", help="人声 loudnorm 目标；含长静音段窗口用 -13.2")
    p.add_argument("--mix-out", default=None, help="混音产物路径（默认 outputs/<name>-音乐响度.mp4）")
    args = p.parse_args()

    master_cfg = json.loads(Path(args.master).read_text(encoding="utf-8"))
    subtitles = json.loads(Path(args.subtitles).read_text(encoding="utf-8"))
    highlight = subtitles.get("highlight", {})
    overlay = json.loads(Path(args.overlay).read_text(encoding="utf-8"))
    kf_root = Path(args.keyframes)
    style, scene_map = extract_keyframes(kf_root / "index.html")
    overrides = master_cfg.get("style_overrides", {})

    cfg = {
        "master_video": Path(master_cfg["path"]),
        "expected_inode": master_cfg.get("expected_inode"),
        "fps": int(master_cfg.get("fps", 60)),
        "color_blue": overrides.get("blue", D.COLOR_BLUE),
        "color_red": overrides.get("red", D.COLOR_RED),
        "color_amber": overrides.get("amber", D.COLOR_AMBER),
        "accent_terms": tuple(highlight.get("accent", ())),
        "risk_terms": tuple(highlight.get("risk", ())),
        "overlay": overlay, "subtitles": subtitles,
        "kf_root": kf_root, "style": style, "scene_map": scene_map,
        "do_check": args.check,
    }
    out_parent = Path(args.out_dir)

    try:
        if args.render or args.mix:
            video = run_render(cfg, args.start, args.end, args.name, args.title, out_parent)
        else:
            project = build_project(cfg, args.start, args.end, args.name, args.title, out_parent)
            if args.check:
                run_check(project)
            return
    except AssertionError as e:
        fail("generate", str(e))

    if args.mix:
        if not args.bgm:
            fail("mix", "未指定 BGM：请用 --bgm 传入音乐文件（首次使用请先按 references/setup.md 第四步配置音乐库）")
        if not Path(args.bgm).is_file():
            fail("mix", f"BGM 文件不存在: {args.bgm}")
        mix_out = Path(args.mix_out) if args.mix_out else (
            out_parent / args.name / "outputs" / f"{args.name}-音乐响度.mp4")
        mix_out.parent.mkdir(parents=True, exist_ok=True)
        run_mix(video, Path(args.bgm), args.voice_i, mix_out)


if __name__ == "__main__":
    main()
