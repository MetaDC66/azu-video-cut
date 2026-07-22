#!/usr/bin/env python3
"""
mix_finalize.py — 视频发布混音一键收口（口播知识短视频工作流）

把混音链固化为一条命令：
  人声 loudnorm 两遍法 → BGM 循环/交叉淡化/垫底 → amix → alimiter 梯度自适应
  → ebur128 实测验收（-14±0.3 LUFS / ≤-1.5 dBTP）→ 视频流 copy 不重编码

用法：
  python3 mix_finalize.py --video 母版.mp4 --bgm /path/to/bgm.wav \
      --out 输出.mp4 [--voice-i -16] [--report report.json]

规则（来自工作流固定规则与经验沉淀，详见 references/workflow.md）：
  - >150s 长片 alimiter 从 0.79 起步，短片从 0.83 起步；不达标按 0.83→0.80→0.79→0.76 梯度收紧
  - 含长静音段的窗口人声目标用 -13.2（--voice-i -13.2），默认 -16
  - BGM 垫底目标约 -30 LUFS（按 BGM 实测响度自动算增益，不写死 -15.4dB）
  - BGM 循环缝 0.5s acrossfade，头 0.3s 尾 0.5s 淡化
  - 响度微调用纯 volume 电平线性收口（-0.4dB → -0.4 LU），不重跑全链
  - 视频流 copy，音频 AAC 256k 48kHz faststart
输出：stdout 仅打印一行紧凑 JSON 报告（省 token），详细数据写 --report 文件。
"""
import argparse, json, re, subprocess, sys, math, os

def run(cmd, capture=True):
    r = subprocess.run(cmd, capture_output=capture, text=True)
    return r

def ffprobe_duration(path):
    r = run(["ffprobe","-v","error","-show_entries","format=duration",
             "-of","default=nw=1:nk=1",path])
    return float(r.stdout.strip())

def loudnorm_measure(video):
    r = run(["ffmpeg","-hide_banner","-i",video,"-vn",
             "-af","loudnorm=I=-16:TP=-3:LRA=11:print_format=json","-f","null","-"])
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S)
    return json.loads(m.group(0))

def ebur128_measure(path):
    r = run(["ffmpeg","-hide_banner","-nostats","-i",path,
             "-af","ebur128=peak=true","-f","null","-"])
    tail = r.stderr[-4000:]
    i_m = re.findall(r"I:\s+(-?[\d.]+)\s+LUFS", tail)
    tp_m = re.findall(r"Peak:\s+(-?[\d.]+)\s+dBFS", tail)
    return (float(i_m[-1]) if i_m else None, float(tp_m[-1]) if tp_m else None)

def build_filter(video_dur, voice_i, ln, bgm_gain, limiter, bgm_dur,
                 extra_volume_db=0.0):
    """构造 filter_complex。BGM 循环用 acrossfade 0.5s 链。"""
    n_loops = max(1, math.ceil(video_dur / bgm_dur))
    parts = []
    # 人声两遍法（dynamic，注入实测值）
    parts.append(
        "[0:a]loudnorm=I=%s:TP=-3:LRA=11:"
        "measured_I=%s:measured_TP=%s:measured_LRA=%s:measured_thresh=%s:"
        "offset=%s:linear=false[voice]" % (
            voice_i, ln["input_i"], ln["input_tp"], ln["input_lra"],
            ln["input_thresh"], ln["target_offset"]))
    # BGM：asplit 成 n 份，acrossfade 0.5s 串联
    if n_loops == 1:
        parts.append("[1:a]atrim=0:%s,volume=%.2fdB[bgm]" % (video_dur, bgm_gain))
    else:
        parts.append("[1:a]asplit=%d%s" % (n_loops,
            "".join("[b%d]" % i for i in range(n_loops))))
        prev = "b0"
        for i in range(1, n_loops):
            out = "x%d" % i
            parts.append("[%s][b%d]acrossfade=d=0.5:c1=tri:c2=tri[%s]" % (prev, i, out))
            prev = out
        parts.append("[%s]atrim=0:%.3f,volume=%.2fdB[bgm]" % (prev, video_dur, bgm_gain))
    parts.append("[bgm]afade=t=in:st=0:d=0.3,afade=t=out:st=%.3f:d=0.5[bgmf]"
                 % max(0.0, video_dur - 0.5))
    vol = 2.2 + extra_volume_db
    parts.append("[voice][bgmf]amix=inputs=2:normalize=0,volume=%.2fdB,"
                 "alimiter=limit=%s:level=false[out]" % (vol, limiter))
    return ";".join(parts)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--bgm", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--voice-i", default="-16")
    ap.add_argument("--report", default=None)
    a = ap.parse_args()

    dur = ffprobe_duration(a.video)
    bgm_dur = ffprobe_duration(a.bgm)
    bgm_i, _ = ebur128_measure(a.bgm)
    bgm_gain = -30.0 - bgm_i                      # 垫底至约 -30 LUFS
    ln = loudnorm_measure(a.video)

    # 限幅器梯度：长片从 0.79 起步
    ladder = [0.79, 0.76, 0.72] if dur > 150 else [0.83, 0.80, 0.79, 0.76]
    attempts = []
    final = None
    for limiter in ladder:
        fc = build_filter(dur, a.voice_i, ln, bgm_gain, limiter, bgm_dur)
        r = run(["ffmpeg","-y","-hide_banner","-loglevel","error",
                 "-i",a.video,"-i",a.bgm,"-filter_complex",fc,
                 "-map","0:v","-c:v","copy","-map","[out]",
                 "-c:a","aac","-b:a","256k","-ar","48000","-ac","2",
                 "-movflags","+faststart",a.out])
        if r.returncode != 0:
            print(json.dumps({"ok":False,"stage":"encode","err":r.stderr[-500:]})); sys.exit(1)
        i_lufs, tp = ebur128_measure(a.out)
        attempts.append({"limiter":limiter,"I":i_lufs,"TP":tp})
        if i_lufs is not None and abs(i_lufs + 14) <= 0.3 and tp <= -1.5:
            final = {"limiter":limiter,"I":i_lufs,"TP":tp,"fine_trim_db":0.0}
            break
        # 电平线性微调：响度差用纯 volume 收口，不收紧限幅器重压
        if i_lufs is not None and abs(i_lufs + 14) > 0.3 and tp <= -1.2:
            delta = -14.0 - i_lufs
            if abs(delta) <= 1.0:
                fc = build_filter(dur, a.voice_i, ln, bgm_gain, limiter, bgm_dur,
                                  extra_volume_db=delta)
                run(["ffmpeg","-y","-hide_banner","-loglevel","error",
                     "-i",a.video,"-i",a.bgm,"-filter_complex",fc,
                     "-map","0:v","-c:v","copy","-map","[out]",
                     "-c:a","aac","-b:a","256k","-ar","48000","-ac","2",
                     "-movflags","+faststart",a.out])
                i2, tp2 = ebur128_measure(a.out)
                attempts.append({"limiter":limiter,"fine_trim_db":round(delta,2),
                                 "I":i2,"TP":tp2})
                if i2 is not None and abs(i2 + 14) <= 0.3 and tp2 <= -1.5:
                    final = {"limiter":limiter,"I":i2,"TP":tp2,
                             "fine_trim_db":round(delta,2)}
                    break
    report = {
        "ok": final is not None,
        "video_dur": round(dur,3), "bgm_dur": round(bgm_dur,3),
        "bgm_measured_I": bgm_i, "bgm_gain_db": round(bgm_gain,2),
        "voice_target_I": a.voice_i,
        "voice_measured": {"I":ln["input_i"],"TP":ln["input_tp"],
                           "LRA":ln["input_lra"],"thresh":ln["input_thresh"]},
        "attempts": attempts, "final": final, "out": os.path.abspath(a.out),
    }
    if a.report:
        with open(a.report,"w") as f: json.dump(report,f,ensure_ascii=False,indent=2)
    # stdout 只出一行紧凑结论（省 token）
    if final:
        print(json.dumps({"ok":True,"I":final["I"],"TP":final["TP"],
                          "limiter":final["limiter"],
                          "fine_trim_db":final["fine_trim_db"],
                          "attempts":len(attempts)}, ensure_ascii=False))
    else:
        print(json.dumps({"ok":False,"attempts":attempts}, ensure_ascii=False))
        sys.exit(2)

if __name__ == "__main__":
    main()
